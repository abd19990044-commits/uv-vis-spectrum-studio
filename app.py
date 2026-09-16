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

APP_NAME = "UV-Vis Spectrum Studio"
COLORS = ["#2563EB", "#DC2626", "#059669", "#7C3AED", "#EA580C", "#0891B2", "#DB2777", "#475569"]
LINE_STYLES = {
    "Solid ━━━": "solid",
    "Dashed ━ ━": "dash",
    "Dotted · · ·": "dot",
    "Dash-dot ━ ·": "dashdot",
    "Long dash ━━  ━━": "longdash",
    "Long dash-dot ━━ ·": "longdashdot",
}
BW_STYLES = ["solid", "dash", "dot", "dashdot", "longdash", "longdashdot"]
FONT_FAMILIES = ["Arial", "Times New Roman", "Calibri", "Cambria", "Georgia", "Verdana", "Courier New"]

st.set_page_config(page_title=APP_NAME, page_icon="🔬", layout="wide", initial_sidebar_state="expanded")
st.markdown(
    """
<style>
.stApp{background:#f7f9fc}.block-container{padding-top:1.1rem;max-width:1650px}
[data-testid="stSidebar"]{background:#fff;border-right:1px solid #e5e7eb}
.hero{padding:1.15rem 1.35rem;border:1px solid #dbe4f0;border-radius:18px;background:linear-gradient(135deg,#fff,#eef6ff);box-shadow:0 8px 24px rgba(15,23,42,.05);margin-bottom:.9rem}
.hero h1{margin:0;color:#0f172a;font-size:2rem}.hero p{margin:.35rem 0 0;color:#475569}
.step{padding:.75rem .95rem;background:#fff;border:1px solid #e5e7eb;border-radius:14px;min-height:80px}.step b{color:#0f172a}.step small{color:#64748b}
div[data-testid="stMetric"]{background:#fff;border:1px solid #e5e7eb;border-radius:14px;padding:.65rem .85rem}.stButton>button,.stDownloadButton>button{border-radius:10px;min-height:2.5rem}
.pubnote{padding:.7rem .9rem;border-left:4px solid #334155;background:#f8fafc;border-radius:8px;color:#334155}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="hero"><h1>🔬 UV-Vis Spectrum Studio</h1><p>Professional UV–Vis plotting, derivative spectroscopy, quantitative spectral metrics and publication-ready export.</p></div>',
    unsafe_allow_html=True,
)
a, b, c = st.columns(3)
with a:
    st.markdown('<div class="step"><b>1 · Load</b><br><small>Excel/CSV/TXT with automatic wavelength detection.</small></div>', unsafe_allow_html=True)
with b:
    st.markdown('<div class="step"><b>2 · Analyze</b><br><small>Derivatives, AUC, λmax, FWHM, peaks, smoothing and baseline.</small></div>', unsafe_allow_html=True)
with c:
    st.markdown('<div class="step"><b>3 · Publish</b><br><small>Color or black-and-white figures, line styles, PNG/SVG/PDF.</small></div>', unsafe_allow_html=True)


def demo_spectra():
    x = np.linspace(200, 800, 1201)
    y1 = 0.08 + 1.02 * np.exp(-0.5 * ((x - 272) / 17) ** 2) + 0.34 * np.exp(-0.5 * ((x - 330) / 31) ** 2)
    y2 = 0.05 + 0.83 * np.exp(-0.5 * ((x - 301) / 22) ** 2) + 0.27 * np.exp(-0.5 * ((x - 365) / 38) ** 2)
    return [
        {"name": "Demo A", "x": x, "y": y1, "color": COLORS[0], "dash": "solid", "source": "Built-in demo", "column": "Absorbance"},
        {"name": "Demo B", "x": x, "y": y2, "color": COLORS[1], "dash": "dash", "source": "Built-in demo", "column": "Absorbance"},
    ]


with st.sidebar:
    st.markdown("### Workspace")
    mode = st.radio("Interface mode", ["Basic", "Advanced"], horizontal=True, help="Basic keeps routine controls visible. Advanced adds preprocessing and peak controls.")
    use_demo = st.toggle("Use built-in demo spectra", False)
    st.divider()
    st.markdown("### 1 · Load data")
    files = st.file_uploader(
        "Drop UV–Vis files here",
        type=["xlsx", "xls", "xlsm", "csv", "txt", "dat", "asc", "tsv"],
        accept_multiple_files=True,
    )
    st.caption("Accepted: Excel, CSV, TXT, DAT, ASC and TSV.")

spectra = []
errors = []
if use_demo:
    spectra = demo_spectra()
elif files:
    for i, up in enumerate(files):
        try:
            df = read_table(BytesIO(up.getvalue()), up.name)
            auto = detect_wavelength_column(df)
            options = [str(c) for c in df.columns]
            with st.sidebar.expander(f"⚙️ {up.name}", expanded=i == 0):
                xcol = st.selectbox("Wavelength column", options, index=options.index(auto), key=f"x{i}")
                yopts = numeric_signal_columns(df, xcol)
                ys = st.multiselect("Signal columns", yopts, default=yopts[:1], key=f"y{i}")
                for j, ycol in enumerate(ys):
                    x, y = clean_xy(df, xcol, ycol)
                    default = Path(up.name).stem if len(ys) == 1 else f"{Path(up.name).stem} · {ycol}"
                    name = st.text_input("Curve name", default, key=f"n{i}_{j}")
                    c1, c2 = st.columns(2)
                    color = c1.color_picker("Color", COLORS[len(spectra) % len(COLORS)], key=f"c{i}_{j}")
                    style_label = c2.selectbox("Line style", list(LINE_STYLES), index=len(spectra) % 4, key=f"ls{i}_{j}")
                    spectra.append(
                        {
                            "name": name,
                            "x": x,
                            "y": y,
                            "color": color,
                            "dash": LINE_STYLES[style_label],
                            "source": up.name,
                            "column": ycol,
                        }
                    )
        except Exception as exc:
            errors.append(f"{up.name}: {exc}")

for e in errors:
    st.error(e)
if not spectra:
    st.info("👈 Upload one or more spectra, or enable **Use built-in demo spectra**.")
    with st.expander("Recommended file format"):
        st.markdown("Use a wavelength column plus one or more signal columns. The wavelength column may have any name; the app detects a numeric column whose first finite value is 200 nm or higher, and you can override it.")
    st.stop()

allx = np.concatenate([s["x"] for s in spectra])
xlo, xhi = float(np.nanmin(allx)), float(np.nanmax(allx))

with st.sidebar:
    st.divider()
    st.markdown("### 2 · Spectral analysis")
    derivative_order = st.selectbox(
        "Spectrum / derivative",
        [0, 1, 2],
        format_func=lambda v: ["Original spectrum", "First derivative (1D)", "Second derivative (2D)"][v],
        help="Derivative spectroscopy can resolve overlapping bands. Smoothing before differentiation is often useful for noisy spectra.",
    )
    st.caption("This control is always visible because derivatives are a core spectroscopy function.")

    crop = st.toggle("Limit wavelength range", False)
    p, q = st.columns(2)
    xmin = p.number_input("X min", value=xlo, disabled=not crop)
    xmax = q.number_input("X max", value=xhi, disabled=not crop)

    auc_enabled = st.toggle("Calculate AUC in a selected range", True)
    p, q = st.columns(2)
    auc_min = p.number_input("AUC from", value=xlo, disabled=not auc_enabled)
    auc_max = q.number_input("AUC to", value=xhi, disabled=not auc_enabled)
    shade_auc = st.toggle("Shade AUC region on graph", False, disabled=not auc_enabled)

    smooth = False
    window = 11
    poly = 3
    baseline = False
    blam = 1_000_000.0
    bp = 0.01
    norm = "None"
    peak_prominence_pct = 3.0
    peak_distance = 1

    if mode == "Advanced":
        st.markdown("#### Preprocessing")
        smooth = st.toggle("Savitzky–Golay smoothing", False)
        p, q = st.columns(2)
        window = p.number_input("Window", 3, 101, 11, 2, disabled=not smooth)
        poly = q.number_input("Polynomial", 1, 7, 3, 1, disabled=not smooth)
        baseline = st.toggle("ALS baseline correction", False)
        blam = st.number_input("Baseline λ", 1.0, value=1_000_000.0, format="%.0f", disabled=not baseline)
        bp = st.number_input("Baseline p", 0.0001, 0.5, 0.01, format="%.4f", disabled=not baseline)
        norm = st.selectbox("Normalization", ["None", "Max = 1", "Min-Max 0–1", "Area = 1"])
        st.markdown("#### Peak detection")
        peak_prominence_pct = st.slider("Minimum prominence (% of Y range)", 0.1, 50.0, 3.0, 0.1)
        peak_distance = st.number_input("Minimum peak distance (points)", 1, 10000, 1, 1)

    st.divider()
    st.markdown("### 3 · Figure & publication style")
    title = st.text_input("Figure title", "UV–Vis spectra")
    xtitle = st.text_input("X-axis title", "Wavelength (nm)")
    y_default = "Absorbance (a.u.)" if derivative_order == 0 else ("dA/dλ" if derivative_order == 1 else "d²A/dλ²")
    ytitle = st.text_input("Y-axis title", y_default)

    bw_mode = st.toggle(
        "Black & white publication mode",
        False,
        help="For journals that require monochrome figures. Curves are distinguished by line pattern instead of color.",
    )
    if bw_mode:
        st.caption("All curves are black; solid/dashed/dotted patterns remain distinguishable in print.")

    font_family = st.selectbox("Figure font", FONT_FAMILIES, index=0)
    linewidth = st.slider("Line width", 0.5, 6.0, 2.2, 0.1)
    fontsize = st.slider("Axis / legend text size", 8, 32, 15)
    titlesize = st.slider("Title size", 10, 40, 20)
    grid = st.toggle("Show grid", False)
    legend = st.toggle("Show legend", True)
    legendpos = st.selectbox("Legend position", ["Top right", "Top left", "Bottom right", "Bottom left", "Outside right"])
    manual_y = st.toggle("Set Y-axis range manually", False)
    p, q = st.columns(2)
    ymin = p.number_input("Y min", value=0.0, disabled=not manual_y)
    ymax = q.number_input("Y max", value=1.0, disabled=not manual_y)
    offset = st.number_input("Vertical offset between curves", value=0.0, step=0.05)

processed = []
for idx, s in enumerate(spectra):
    x, y = crop_xy(s["x"], s["y"], xmin if crop else None, xmax if crop else None)
    if len(x) < 2:
        continue
    x, yp = process_spectrum(
        x,
        y,
        smooth=smooth,
        window=int(window),
        polyorder=int(poly),
        baseline=baseline,
        baseline_lambda=float(blam),
        baseline_p=float(bp),
        normalization=norm,
        derivative_order=int(derivative_order),
    )
    processed.append({**s, "x": x, "analysis_y": yp, "plot_y": yp + idx * float(offset)})

if not processed:
    st.error("No data remain in the selected wavelength range.")
    st.stop()

fig = go.Figure()
for idx, s in enumerate(processed):
    dash = BW_STYLES[idx % len(BW_STYLES)] if bw_mode else s["dash"]
    color = "#000000" if bw_mode else s["color"]
    fig.add_trace(
        go.Scatter(
            x=s["x"],
            y=s["plot_y"],
            mode="lines",
            name=s["name"],
            line=dict(color=color, width=linewidth, dash=dash),
            hovertemplate=f"<b>{s['name']}</b><br>λ = %{{x:.4f}} nm<br>Signal = %{{y:.7g}}<extra></extra>",
        )
    )

    if auc_enabled and shade_auc:
        mask = (s["x"] >= min(auc_min, auc_max)) & (s["x"] <= max(auc_min, auc_max))
        if np.count_nonzero(mask) >= 2:
            fig.add_trace(
                go.Scatter(
                    x=s["x"][mask],
                    y=s["plot_y"][mask],
                    fill="tozeroy",
                    mode="none",
                    fillcolor="rgba(80,80,80,0.10)" if bw_mode else "rgba(37,99,235,0.08)",
                    showlegend=False,
                    hoverinfo="skip",
                )
            )

pos = {
    "Top right": dict(x=0.99, y=0.99, xanchor="right", yanchor="top"),
    "Top left": dict(x=0.01, y=0.99, xanchor="left", yanchor="top"),
    "Bottom right": dict(x=0.99, y=0.01, xanchor="right", yanchor="bottom"),
    "Bottom left": dict(x=0.01, y=0.01, xanchor="left", yanchor="bottom"),
    "Outside right": dict(x=1.02, y=1.0, xanchor="left", yanchor="top"),
}
fig.update_layout(
    title=dict(text=title, font=dict(size=titlesize, family=font_family), x=0.5, xanchor="center"),
    xaxis_title=xtitle,
    yaxis_title=ytitle,
    font=dict(size=fontsize, family=font_family, color="#000000"),
    template="plotly_white",
    hovermode="closest",
    showlegend=legend,
    legend=pos[legendpos],
    margin=dict(l=80, r=145 if legendpos == "Outside right" else 35, t=75, b=70),
    paper_bgcolor="white",
    plot_bgcolor="white",
)
fig.update_xaxes(
    showgrid=grid,
    gridcolor="#d1d5db",
    mirror=True,
    ticks="outside",
    showline=True,
    linewidth=1.2,
    linecolor="#111827",
    showspikes=True,
    spikemode="across",
    spikesnap="cursor",
    spikedash="dot",
)
fig.update_yaxes(
    showgrid=grid,
    gridcolor="#d1d5db",
    mirror=True,
    ticks="outside",
    showline=True,
    linewidth=1.2,
    linecolor="#111827",
    showspikes=True,
    spikemode="across",
    spikesnap="cursor",
    spikedash="dot",
)
if crop:
    fig.update_xaxes(range=[xmin, xmax])
if manual_y:
    fig.update_yaxes(range=[ymin, ymax])

metrics = []
auc_rows = []
peaks = []
merged = None
for s in processed:
    y_analysis = s["analysis_y"]
    yrange = float(np.nanmax(y_analysis) - np.nanmin(y_analysis)) if len(y_analysis) else 0.0
    prominence = max(yrange * float(peak_prominence_pct) / 100.0, np.finfo(float).eps)
    metrics.append({"Curve": s["name"], **asdict(calculate_metrics(s["x"], y_analysis, prominence=prominence))})
    peaks.extend(
        [
            {"Curve": s["name"], **p}
            for p in peak_table(s["x"], y_analysis, prominence=prominence, distance=int(peak_distance))
        ]
    )

    if auc_enabled:
        xa, ya = crop_xy(s["x"], y_analysis, min(auc_min, auc_max), max(auc_min, auc_max))
        if len(xa) >= 2:
            signed_auc = float(np.trapezoid(ya, xa))
            absolute_auc = float(np.trapezoid(np.abs(ya), xa))
            auc_rows.append(
                {
                    "Curve": s["name"],
                    "From (nm)": float(xa[0]),
                    "To (nm)": float(xa[-1]),
                    "Signed AUC": signed_auc,
                    "Absolute AUC": absolute_auc,
                }
            )

    part = pd.DataFrame({"Wavelength_nm": s["x"], s["name"]: y_analysis})
    merged = part if merged is None else pd.merge(merged, part, on="Wavelength_nm", how="outer")

merged = merged.sort_values("Wavelength_nm")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Curves loaded", len(processed))
m2.metric("Wavelength range", f"{min(float(s['x'][0]) for s in processed):.1f}–{max(float(s['x'][-1]) for s in processed):.1f} nm")
m3.metric("Displayed", ["Original", "1st derivative", "2nd derivative"][derivative_order])
m4.metric("B&W mode", "On" if bw_mode else "Off")

plot_tab, analysis_tab, derivative_tab, data_tab, export_tab, help_tab = st.tabs(
    ["📈 Spectrum", "🧪 Analysis", "∂ Derivatives & AUC", "📋 Data", "💾 Export", "❓ Help"]
)

with plot_tab:
    st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False, "scrollZoom": True, "responsive": True})
    st.caption("Hover for exact wavelength/signal values. Drag or scroll to zoom; double-click to reset.")
    if bw_mode:
        st.markdown('<div class="pubnote"><b>Black & white publication mode:</b> curve identity is encoded by line pattern, so the figure remains interpretable when printed in grayscale.</div>', unsafe_allow_html=True)

with analysis_tab:
    md = pd.DataFrame(metrics).rename(
        columns={
            "lambda_max": "λmax (nm)",
            "y_max": "Signal at λmax",
            "lambda_min": "λmin (nm)",
            "y_min": "Signal at λmin",
            "area": "Signed AUC (full range)",
            "absolute_area": "Absolute AUC (full range)",
            "centroid": "Centroid (nm)",
            "fwhm": "FWHM (nm)",
            "peak_count": "Peaks",
        }
    )
    st.markdown("#### Spectral metrics")
    st.dataframe(md, use_container_width=True, hide_index=True)
    st.caption("Signed AUC preserves positive/negative derivative lobes. Absolute AUC integrates magnitude and is often more informative for derivative spectra.")

    st.markdown("#### Detected peaks")
    pdp = pd.DataFrame(peaks).rename(
        columns={
            "wavelength_nm": "Wavelength (nm)",
            "intensity": "Signal",
            "prominence": "Prominence",
            "fwhm_nm": "FWHM (nm)",
        }
    )
    st.dataframe(pdp, use_container_width=True, hide_index=True) if not pdp.empty else st.info("No peaks met the selected prominence criterion.")

with derivative_tab:
    st.markdown("#### Derivative spectroscopy")
    st.write(
        "Choose **Original**, **First derivative**, or **Second derivative** from the sidebar. "
        "The selected derivative is calculated with respect to wavelength. On uniformly spaced data the app uses Savitzky–Golay differentiation; irregular grids use coordinate-aware numerical gradients."
    )
    if derivative_order > 0 and not smooth:
        st.warning("Derivatives amplify high-frequency noise. For noisy experimental spectra, consider enabling Savitzky–Golay smoothing in Advanced mode and document the chosen window/order.")

    st.markdown("#### Area under the curve (AUC)")
    if auc_enabled and auc_rows:
        st.dataframe(pd.DataFrame(auc_rows), use_container_width=True, hide_index=True)
        st.caption("AUC is calculated from the processed spectrum before any visual vertical offset is added.")
    elif auc_enabled:
        st.info("The selected AUC interval does not contain enough data points.")
    else:
        st.info("Enable AUC calculation in the sidebar to select an integration interval.")

with data_tab:
    st.dataframe(merged, use_container_width=True, hide_index=True, height=460)
    st.caption("These are processed analytical values. Visual vertical offsets used for display are intentionally excluded.")

with export_tab:
    st.markdown("#### Publication export")
    st.caption("600 DPI is a strong journal default. SVG and PDF remain vector formats and are preferable where accepted.")
    e1, e2, e3 = st.columns(3)
    win = e1.number_input("Width (inches)", 2.0, 20.0, 7.0, 0.25)
    hin = e2.number_input("Height (inches)", 2.0, 20.0, 5.0, 0.25)
    dpi = e3.select_slider("PNG resolution", [300, 600, 720, 900, 1200], 600, format_func=lambda x: f"{x} DPI")
    st.info(f"PNG output: **{round(win * dpi):,} × {round(hin * dpi):,} pixels** at **{dpi} DPI**.")
    if bw_mode:
        st.success("Current export is configured for monochrome publication with distinct line styles.")
    d1, d2, d3, d4 = st.columns(4)
    try:
        d1.download_button(f"Download PNG · {dpi} DPI", figure_png_bytes(fig, win, hin, int(dpi)), "uvvis_spectrum.png", "image/png", use_container_width=True)
    except Exception as exc:
        d1.warning(f"PNG unavailable: {exc}")
    try:
        d2.download_button("Download SVG", figure_vector_bytes(fig, "svg", win, hin), "uvvis_spectrum.svg", "image/svg+xml", use_container_width=True)
    except Exception:
        d2.button("SVG unavailable", disabled=True, use_container_width=True)
    try:
        d3.download_button("Download PDF", figure_vector_bytes(fig, "pdf", win, hin), "uvvis_spectrum.pdf", "application/pdf", use_container_width=True)
    except Exception:
        d3.button("PDF unavailable", disabled=True, use_container_width=True)
    d4.download_button("Processed CSV", merged.to_csv(index=False).encode("utf-8-sig"), "uvvis_processed.csv", "text/csv", use_container_width=True)

    if auc_rows:
        st.download_button("Download AUC table (CSV)", pd.DataFrame(auc_rows).to_csv(index=False).encode("utf-8-sig"), "uvvis_auc.csv", "text/csv")

with help_tab:
    st.markdown(
        """#### Quick guide
1. Upload one or more spectra from the left panel.
2. Confirm the detected wavelength column and choose signal columns.
3. Choose a **line style for every curve**; use **Black & white publication mode** when color is not permitted.
4. Select **Original / First derivative / Second derivative** under Spectral analysis.
5. Define an AUC interval and optionally shade it on the graph.
6. In Advanced mode, apply smoothing/baseline/normalization only when analytically justified.
7. Review λmax, λmin, AUC, centroid, FWHM and detected peaks in Analysis.
8. Export PNG (300–1200 DPI), SVG, PDF or processed CSV.

**Scientific note:** The app never uses visual vertical offsets in λmax, peak, FWHM or AUC calculations. Original uploaded files are not modified.
"""
    )

st.divider()
st.caption("UV-Vis Spectrum Studio · scientific plotting and spectroscopy analysis")
