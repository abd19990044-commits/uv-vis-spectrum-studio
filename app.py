from __future__ import annotations

from dataclasses import asdict
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from uvvis_studio.analysis import calculate_metrics, crop_xy, peak_table, process_spectrum
from uvvis_studio.export import figure_png_bytes, figure_vector_bytes
from uvvis_studio.io import clean_xy, detect_wavelength_column, numeric_signal_columns, read_table

st.set_page_config(page_title="UV-Vis Spectrum Studio", page_icon="📈", layout="wide")

DEFAULT_COLORS = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf", "#8c564b", "#e377c2"]

st.title("UV-Vis Spectrum Studio")
st.caption("Publication-grade UV–Vis plotting, preprocessing and spectral analysis from Excel / TXT / CSV files.")

with st.sidebar:
    st.header("1 · Data")
    files = st.file_uploader(
        "Upload spectra",
        type=["xlsx", "xls", "xlsm", "csv", "txt", "dat", "asc", "tsv"],
        accept_multiple_files=True,
        help="For automatic detection, the wavelength column should begin with a numeric value of 200 nm or greater.",
    )

if not files:
    st.info("Upload one or more UV–Vis files to begin. The wavelength column is detected automatically using the ≥200 nm rule, and can be overridden manually.")
    st.stop()

spectra = []
errors = []
for file_i, up in enumerate(files):
    try:
        raw = up.getvalue()
        df = read_table(BytesIO(raw), up.name)
        auto_x = detect_wavelength_column(df)
        x_options = [str(c) for c in df.columns]
        with st.sidebar.expander(f"{up.name}", expanded=(file_i == 0)):
            x_col = st.selectbox("Wavelength column", x_options, index=x_options.index(auto_x), key=f"x_{file_i}")
            y_opts = numeric_signal_columns(df, x_col)
            if not y_opts:
                st.warning("No numeric signal columns found.")
                continue
            selected_y = st.multiselect("Signal columns", y_opts, default=y_opts[:1], key=f"y_{file_i}")
            for j, y_col in enumerate(selected_y):
                x, y = clean_xy(df, x_col, y_col)
                default_name = Path(up.name).stem if len(y_opts) == 1 else f"{Path(up.name).stem} · {y_col}"
                name = st.text_input(f"Curve name · {y_col}", value=default_name, key=f"name_{file_i}_{j}")
                color = st.color_picker(f"Color · {y_col}", DEFAULT_COLORS[len(spectra) % len(DEFAULT_COLORS)], key=f"color_{file_i}_{j}")
                spectra.append({"name": name, "x": x, "y": y, "color": color, "source": up.name, "column": y_col})
    except Exception as exc:
        errors.append(f"{up.name}: {exc}")

if errors:
    for e in errors:
        st.error(e)
if not spectra:
    st.stop()

with st.sidebar:
    st.header("2 · Processing")
    all_x = np.concatenate([s["x"] for s in spectra])
    xmin_data, xmax_data = float(np.nanmin(all_x)), float(np.nanmax(all_x))
    crop_on = st.checkbox("Crop wavelength range", False)
    c1, c2 = st.columns(2)
    xmin = c1.number_input("X min", value=xmin_data, disabled=not crop_on)
    xmax = c2.number_input("X max", value=xmax_data, disabled=not crop_on)

    smooth = st.checkbox("Savitzky–Golay smoothing", False)
    c1, c2 = st.columns(2)
    window = c1.number_input("Window", min_value=3, value=11, step=2, disabled=not smooth)
    polyorder = c2.number_input("Polynomial", min_value=1, value=3, disabled=not smooth)

    baseline = st.checkbox("ALS baseline correction", False)
    baseline_lambda = st.number_input("Baseline λ", min_value=1.0, value=1_000_000.0, format="%.0f", disabled=not baseline)
    baseline_p = st.number_input("Baseline p", min_value=0.0001, max_value=0.5, value=0.01, format="%.4f", disabled=not baseline)
    normalization = st.selectbox("Normalization", ["None", "Max = 1", "Min-Max 0–1", "Area = 1"])
    derivative_order = st.selectbox("Derivative", [0, 1, 2], format_func=lambda v: ["Original", "First derivative", "Second derivative"][v])
    y_offset = st.number_input("Vertical offset between curves", value=0.0, step=0.05)

    st.header("3 · Figure")
    title = st.text_input("Figure title", "UV–Vis spectra")
    x_title = st.text_input("X-axis title", "Wavelength (nm)")
    y_default = "Absorbance (a.u.)" if derivative_order == 0 else ("dA/dλ" if derivative_order == 1 else "d²A/dλ²")
    y_title = st.text_input("Y-axis title", y_default)
    font_size = st.slider("Base font size", 8, 36, 16)
    title_size = st.slider("Title font size", 10, 44, 20)
    line_width = st.slider("Line width", 0.5, 6.0, 2.0, 0.1)
    show_grid = st.checkbox("Grid", False)
    show_legend = st.checkbox("Legend", True)
    legend_position = st.selectbox("Legend position", ["Top right", "Top left", "Bottom right", "Bottom left", "Outside right"])

    manual_y = st.checkbox("Manual Y range", False)
    c1, c2 = st.columns(2)
    ymin = c1.number_input("Y min", value=0.0, disabled=not manual_y)
    ymax = c2.number_input("Y max", value=1.0, disabled=not manual_y)

    st.header("4 · Export")
    c1, c2 = st.columns(2)
    width_in = c1.number_input("Width (in)", min_value=2.0, max_value=20.0, value=7.0, step=0.25)
    height_in = c2.number_input("Height (in)", min_value=2.0, max_value=20.0, value=5.0, step=0.25)
    dpi = st.select_slider("PNG DPI", options=[300, 600, 720, 900, 1200], value=600)

processed = []
for idx, s in enumerate(spectra):
    x, y = crop_xy(s["x"], s["y"], xmin if crop_on else None, xmax if crop_on else None)
    if len(x) < 2:
        continue
    x, y = process_spectrum(
        x, y,
        smooth=smooth, window=int(window), polyorder=int(polyorder),
        baseline=baseline, baseline_lambda=float(baseline_lambda), baseline_p=float(baseline_p),
        normalization=normalization, derivative_order=int(derivative_order),
    )
    y = y + idx * float(y_offset)
    processed.append({**s, "x": x, "y_processed": y})

if not processed:
    st.error("No data remain after cropping.")
    st.stop()

fig = go.Figure()
for s in processed:
    fig.add_trace(go.Scatter(
        x=s["x"], y=s["y_processed"], mode="lines", name=s["name"],
        line=dict(color=s["color"], width=line_width),
        hovertemplate=f"<b>{s['name']}</b><br>λ = %{{x:.4f}} nm<br>Y = %{{y:.6g}}<extra></extra>",
    ))

legend_map = {
    "Top right": dict(x=0.99, y=0.99, xanchor="right", yanchor="top"),
    "Top left": dict(x=0.01, y=0.99, xanchor="left", yanchor="top"),
    "Bottom right": dict(x=0.99, y=0.01, xanchor="right", yanchor="bottom"),
    "Bottom left": dict(x=0.01, y=0.01, xanchor="left", yanchor="bottom"),
    "Outside right": dict(x=1.02, y=1.0, xanchor="left", yanchor="top"),
}

fig.update_layout(
    title=dict(text=title, font=dict(size=title_size), x=0.5, xanchor="center"),
    xaxis_title=x_title, yaxis_title=y_title,
    font=dict(size=font_size),
    template="plotly_white", hovermode="x unified",
    showlegend=show_legend, legend=legend_map[legend_position],
    margin=dict(l=80, r=80 if legend_position == "Outside right" else 35, t=75, b=70),
)
fig.update_xaxes(showgrid=show_grid, mirror=True, ticks="outside", showline=True, linewidth=1.2,
                 showspikes=True, spikemode="across", spikesnap="cursor", spikedash="dot")
fig.update_yaxes(showgrid=show_grid, mirror=True, ticks="outside", showline=True, linewidth=1.2,
                 showspikes=True, spikemode="across", spikesnap="cursor", spikedash="dot")
if crop_on:
    fig.update_xaxes(range=[xmin, xmax])
if manual_y:
    fig.update_yaxes(range=[ymin, ymax])

st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False, "scrollZoom": True})
st.caption("Use hover/crosshair for precise wavelength and signal readout; drag to zoom and double-click to reset.")

metrics_rows = []
peak_rows = []
for s in processed:
    m = calculate_metrics(s["x"], s["y_processed"])
    row = {"curve": s["name"], **asdict(m)}
    metrics_rows.append(row)
    for p in peak_table(s["x"], s["y_processed"]):
        peak_rows.append({"curve": s["name"], **p})

c1, c2, c3, c4 = st.columns(4)
c1.metric("Curves", len(processed))
c2.metric("λ range", f"{min(float(s['x'][0]) for s in processed):.1f}–{max(float(s['x'][-1]) for s in processed):.1f} nm")
c3.metric("Derivative", derivative_order)
c4.metric("Export", f"{dpi} DPI")

tab1, tab2, tab3 = st.tabs(["Spectral metrics", "Detected peaks", "Processed data"])
with tab1:
    metrics_df = pd.DataFrame(metrics_rows)
    st.dataframe(metrics_df, use_container_width=True, hide_index=True)
with tab2:
    peaks_df = pd.DataFrame(peak_rows)
    st.dataframe(peaks_df, use_container_width=True, hide_index=True)
with tab3:
    merged = None
    for s in processed:
        part = pd.DataFrame({"Wavelength_nm": s["x"], s["name"]: s["y_processed"]})
        merged = part if merged is None else pd.merge(merged, part, on="Wavelength_nm", how="outer")
    merged = merged.sort_values("Wavelength_nm")
    st.dataframe(merged, use_container_width=True, hide_index=True)

st.subheader("Export")
col1, col2, col3, col4 = st.columns(4)
try:
    png = figure_png_bytes(fig, width_in, height_in, int(dpi))
    col1.download_button(f"PNG · {dpi} DPI", png, "uvvis_spectrum.png", "image/png", use_container_width=True)
except Exception as exc:
    col1.warning(f"PNG export unavailable: {exc}")

try:
    svg = figure_vector_bytes(fig, "svg", width_in, height_in)
    col2.download_button("SVG · vector", svg, "uvvis_spectrum.svg", "image/svg+xml", use_container_width=True)
except Exception:
    col2.button("SVG · vector", disabled=True, use_container_width=True)

try:
    pdf = figure_vector_bytes(fig, "pdf", width_in, height_in)
    col3.download_button("PDF · vector", pdf, "uvvis_spectrum.pdf", "application/pdf", use_container_width=True)
except Exception:
    col3.button("PDF · vector", disabled=True, use_container_width=True)

csv_bytes = merged.to_csv(index=False).encode("utf-8-sig")
col4.download_button("Processed CSV", csv_bytes, "uvvis_processed.csv", "text/csv", use_container_width=True)

st.divider()
st.caption("Scientific processing: Savitzky–Golay smoothing/derivatives, asymmetric least-squares baseline correction, normalization, AUC, λmax, centroid, FWHM and peak detection.")
