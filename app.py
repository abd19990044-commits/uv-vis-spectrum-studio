from __future__ import annotations

from dataclasses import asdict
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from uvvis_studio.analysis import (
    absorbance_to_transmittance,
    calculate_metrics,
    crop_xy,
    estimate_snr,
    integrate_range,
    peak_table,
    process_spectrum,
    signal_at_wavelength,
    spectral_arithmetic,
    transmittance_to_absorbance,
    zero_crossings,
)
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
DERIVATIVE_LABELS = ["Original spectrum (0D)", "First derivative (1D)", "Second derivative (2D)", "Third derivative (3D)", "Fourth derivative (4D)"]
DERIVATIVE_Y = ["Absorbance (a.u.)", "dA/dλ", "d²A/dλ²", "d³A/dλ³", "d⁴A/dλ⁴"]

st.set_page_config(page_title=APP_NAME, page_icon="🔬", layout="wide", initial_sidebar_state="expanded")
st.markdown(
    """
<style>
#MainMenu, [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] {display:none !important;}
header[data-testid="stHeader"] {height:0 !important; min-height:0 !important; background:transparent !important;}
.stApp{background:#f7f9fc}.block-container{padding-top:1.0rem;max-width:1700px}
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
    '<div class="hero"><h1>🔬 UV-Vis Spectrum Studio</h1><p>Advanced UV–Vis spectroscopy, derivative analysis, quantitative metrics and publication-ready figures.</p></div>',
    unsafe_allow_html=True,
)
a, b, c = st.columns(3)
with a:
    st.markdown('<div class="step"><b>1 · Load</b><br><small>Excel/CSV/TXT with automatic wavelength detection.</small></div>', unsafe_allow_html=True)
with b:
    st.markdown('<div class="step"><b>2 · Analyze</b><br><small>0D–4D derivatives, AUC, peaks, zero-crossing, S/N and spectral arithmetic.</small></div>', unsafe_allow_html=True)
with c:
    st.markdown('<div class="step"><b>3 · Publish</b><br><small>Color or monochrome figures with independent line styles and high-resolution export.</small></div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### Workspace")
    mode = st.radio("Interface mode", ["Basic", "Advanced"], horizontal=True)
    st.divider()
    st.markdown("### 1 · Load data")
    files = st.file_uploader(
        "Drop UV–Vis files here",
        type=["xlsx", "xls", "xlsm", "csv", "txt", "dat", "asc", "tsv"],
        accept_multiple_files=True,
    )
    st.caption("Accepted: Excel, CSV, TXT, DAT, ASC and TSV.")

spectra: list[dict] = []
errors: list[str] = []
if files:
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
                    spectra.append({
                        "name": name,
                        "x": x,
                        "y": y,
                        "color": color,
                        "dash": LINE_STYLES[style_label],
                        "source": up.name,
                        "column": ycol,
                    })
        except Exception as exc:
            errors.append(f"{up.name}: {exc}")

for e in errors:
    st.error(e)
if not spectra:
    st.info("👈 Upload one or more UV–Vis spectra to begin.")
    with st.expander("Recommended file format"):
        st.markdown("Provide one wavelength column and one or more signal columns. The wavelength column can have any name; automatic detection can be overridden manually.")
    st.stop()

allx = np.concatenate([s["x"] for s in spectra])
xlo, xhi = float(np.nanmin(allx)), float(np.nanmax(allx))

with st.sidebar:
    st.divider()
    st.markdown("### 2 · Spectral processing")
    derivative_order = st.selectbox("Spectrum / derivative", list(range(5)), format_func=lambda v: DERIVATIVE_LABELS[v])
    if derivative_order >= 3:
        st.warning("3D/4D derivatives strongly amplify noise; use smoothing and report the processing parameters in publications.")

    crop = st.toggle("Limit wavelength range", False)
    p, q = st.columns(2)
    xmin = p.number_input("X min", value=xlo, disabled=not crop)
    xmax = q.number_input("X max", value=xhi, disabled=not crop)

    auc_enabled = st.toggle("Calculate AUC in selected range", True)
    p, q = st.columns(2)
    auc_min = p.number_input("AUC from", value=xlo, disabled=not auc_enabled)
    auc_max = q.number_input("AUC to", value=xhi, disabled=not auc_enabled)
    shade_auc = st.toggle("Shade AUC region", False, disabled=not auc_enabled)

    smoothing_method = "None"
    window, poly, gaussian_sigma = 11, 3, 2.0
    baseline_method = "None"
    blam, bp, baseline_poly_order, baseline_edge_fraction = 1_000_000.0, 0.01, 2, 0.10
    norm = "None"
    peak_prominence_pct, peak_distance = 3.0, 1
    conversion = "None"

    if mode == "Advanced":
        st.markdown("#### Smoothing")
        smoothing_method = st.selectbox("Smoothing method", ["None", "Savitzky-Golay", "Moving average", "Gaussian"])
        if smoothing_method in {"Savitzky-Golay", "Moving average"}:
            p, q = st.columns(2)
            window = p.number_input("Window", 3, 201, 11, 2)
            poly = q.number_input("Polynomial order", 1, 9, max(3, derivative_order + 1), 1, disabled=smoothing_method != "Savitzky-Golay")
        if smoothing_method == "Gaussian":
            gaussian_sigma = st.number_input("Gaussian σ (points)", 0.1, 50.0, 2.0, 0.1)

        st.markdown("#### Baseline correction")
        baseline_method = st.selectbox("Baseline method", ["None", "ALS", "Linear endpoints", "Polynomial edges"])
        if baseline_method == "ALS":
            blam = st.number_input("ALS λ", 1.0, value=1_000_000.0, format="%.0f")
            bp = st.number_input("ALS p", 0.0001, 0.5, 0.01, format="%.4f")
        elif baseline_method in {"Linear endpoints", "Polynomial edges"}:
            baseline_edge_fraction = st.slider("Edge fraction used for baseline", 0.02, 0.40, 0.10, 0.01)
            if baseline_method == "Polynomial edges":
                baseline_poly_order = st.number_input("Polynomial order", 1, 5, 2, 1)

        norm = st.selectbox("Normalization", ["None", "Max = 1", "Min-Max 0–1", "Area = 1"])
        conversion = st.selectbox("Signal conversion", ["None", "Absorbance → %Transmittance", "%Transmittance → Absorbance"])

        st.markdown("#### Peak detection")
        peak_prominence_pct = st.slider("Minimum prominence (% of Y range)", 0.1, 50.0, 3.0, 0.1)
        peak_distance = st.number_input("Minimum peak distance (points)", 1, 10000, 1, 1)

    st.divider()
    st.markdown("### 3 · Figure & publication style")
    title = st.text_input("Figure title", "UV–Vis spectra")
    xtitle = st.text_input("X-axis title", "Wavelength (nm)")
    ytitle = st.text_input("Y-axis title", DERIVATIVE_Y[derivative_order])
    bw_mode = st.toggle("Black & white publication mode", False)
    bw_auto = st.toggle("Auto line patterns in B&W", True, disabled=not bw_mode)
    font_family = st.selectbox("Figure font", FONT_FAMILIES, index=1 if "Times New Roman" in FONT_FAMILIES else 0)
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
    label_peaks = st.toggle("Label detected peaks", False)

# Optional arithmetic or reference subtraction creates a derived curve before processing.
if mode == "Advanced" and len(spectra) >= 2:
    with st.sidebar.expander("Spectral arithmetic / blank correction"):
        arithmetic = st.selectbox("Operation", ["None", "Blank/reference subtraction", "Difference A − B", "Ratio A / B", "Add A + B"])
        if arithmetic != "None":
            names = [s["name"] for s in spectra]
            a_name = st.selectbox("Spectrum A", names, index=0)
            b_name = st.selectbox("Spectrum B / reference", names, index=min(1, len(names)-1))
            sa = next(s for s in spectra if s["name"] == a_name)
            sb = next(s for s in spectra if s["name"] == b_name)
            xo, yo = spectral_arithmetic(sa["x"], sa["y"], sb["x"], sb["y"], arithmetic)
            derived_name = st.text_input("Derived curve name", f"{a_name} {arithmetic} {b_name}")
            spectra.append({"name": derived_name, "x": xo, "y": yo, "color": "#111827", "dash": "dashdot", "source": "Derived", "column": arithmetic})

processed = []
for idx, s in enumerate(spectra):
    x, y = crop_xy(s["x"], s["y"], xmin if crop else None, xmax if crop else None)
    if len(x) < 2:
        continue
    if conversion == "Absorbance → %Transmittance":
        y = absorbance_to_transmittance(y)
    elif conversion == "%Transmittance → Absorbance":
        y = transmittance_to_absorbance(y)
    x, yp = process_spectrum(
        x,
        y,
        smoothing_method=smoothing_method,
        window=int(window),
        polyorder=int(poly),
        gaussian_sigma=float(gaussian_sigma),
        baseline_method=baseline_method,
        baseline_lambda=float(blam),
        baseline_p=float(bp),
        baseline_poly_order=int(baseline_poly_order),
        baseline_edge_fraction=float(baseline_edge_fraction),
        normalization=norm,
        derivative_order=int(derivative_order),
    )
    processed.append({**s, "x": x, "analysis_y": yp, "plot_y": yp + idx * float(offset)})

if not processed:
    st.error("No data remain in the selected wavelength range.")
    st.stop()

fig = go.Figure()
all_peak_rows = []
for idx, s in enumerate(processed):
    dash = (BW_STYLES[idx % len(BW_STYLES)] if bw_auto else s["dash"]) if bw_mode else s["dash"]
    color = "#000000" if bw_mode else s["color"]
    fig.add_trace(go.Scatter(
        x=s["x"], y=s["plot_y"], mode="lines", name=s["name"],
        line=dict(color=color, width=linewidth, dash=dash),
        hovertemplate=f"<b>{s['name']}</b><br>λ = %{{x:.4f}} nm<br>Signal = %{{y:.8g}}<extra></extra>",
    ))

    yrange = float(np.nanmax(s["analysis_y"]) - np.nanmin(s["analysis_y"]))
    prominence = max(yrange * peak_prominence_pct / 100.0, np.finfo(float).eps)
    curve_peaks = peak_table(s["x"], s["analysis_y"], prominence=prominence, distance=int(peak_distance))
    for p in curve_peaks:
        all_peak_rows.append({"Curve": s["name"], **p})
    if label_peaks and curve_peaks:
        fig.add_trace(go.Scatter(
            x=[p["wavelength_nm"] for p in curve_peaks],
            y=[signal_at_wavelength(s["x"], s["plot_y"], p["wavelength_nm"]) for p in curve_peaks],
            mode="markers+text", showlegend=False,
            marker=dict(size=6, color=color),
            text=[f"{p['wavelength_nm']:.1f}" for p in curve_peaks], textposition="top center",
            hoverinfo="skip",
        ))

    if auc_enabled and shade_auc:
        _, _, xa, ya = integrate_range(s["x"], s["analysis_y"], auc_min, auc_max)
        if len(xa) >= 2:
            fig.add_trace(go.Scatter(
                x=xa, y=ya + idx * float(offset), fill="tozeroy", mode="none",
                fillcolor="rgba(80,80,80,0.10)" if bw_mode else "rgba(37,99,235,0.08)",
                showlegend=False, hoverinfo="skip",
            ))

pos = {
    "Top right": dict(x=0.99, y=0.99, xanchor="right", yanchor="top"),
    "Top left": dict(x=0.01, y=0.99, xanchor="left", yanchor="top"),
    "Bottom right": dict(x=0.99, y=0.01, xanchor="right", yanchor="bottom"),
    "Bottom left": dict(x=0.01, y=0.01, xanchor="left", yanchor="bottom"),
    "Outside right": dict(x=1.02, y=1.0, xanchor="left", yanchor="top"),
}
fig.update_layout(
    title=dict(text=title, font=dict(size=titlesize, family=font_family), x=0.5, xanchor="center"),
    xaxis_title=xtitle, yaxis_title=ytitle,
    font=dict(size=fontsize, family=font_family, color="#000000"), template="plotly_white",
    hovermode="closest", showlegend=legend, legend=pos[legendpos],
    margin=dict(l=80, r=145 if legendpos == "Outside right" else 35, t=75, b=70),
    paper_bgcolor="white", plot_bgcolor="white",
)
fig.update_xaxes(showgrid=grid, gridcolor="#d1d5db", mirror=True, ticks="outside", showline=True, linewidth=1.2, linecolor="#111827", showspikes=True, spikemode="across", spikesnap="cursor", spikedash="dot")
fig.update_yaxes(showgrid=grid, gridcolor="#d1d5db", mirror=True, ticks="outside", showline=True, linewidth=1.2, linecolor="#111827", showspikes=True, spikemode="across", spikesnap="cursor", spikedash="dot")
if crop:
    fig.update_xaxes(range=[xmin, xmax])
if manual_y:
    fig.update_yaxes(range=[ymin, ymax])

metrics, auc_rows, zero_rows = [], [], []
merged = None
for s in processed:
    y_analysis = s["analysis_y"]
    yrange = float(np.nanmax(y_analysis) - np.nanmin(y_analysis))
    prominence = max(yrange * peak_prominence_pct / 100.0, np.finfo(float).eps)
    metrics.append({"Curve": s["name"], **asdict(calculate_metrics(s["x"], y_analysis, prominence=prominence))})
    if auc_enabled:
        signed_auc, absolute_auc, xa, _ = integrate_range(s["x"], y_analysis, auc_min, auc_max)
        if len(xa) >= 2:
            auc_rows.append({"Curve": s["name"], "From (nm)": float(xa[0]), "To (nm)": float(xa[-1]), "Signed AUC": signed_auc, "Absolute AUC": absolute_auc})
    if derivative_order > 0:
        zero_rows.extend([{"Curve": s["name"], **z} for z in zero_crossings(s["x"], y_analysis, tolerance=max(yrange * 1e-8, 0.0))])
    part = pd.DataFrame({"Wavelength_nm": s["x"], s["name"]: y_analysis})
    merged = part if merged is None else pd.merge(merged, part, on="Wavelength_nm", how="outer")
merged = merged.sort_values("Wavelength_nm")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Curves", len(processed))
m2.metric("Range", f"{min(float(s['x'][0]) for s in processed):.1f}–{max(float(s['x'][-1]) for s in processed):.1f} nm")
m3.metric("Displayed", DERIVATIVE_LABELS[derivative_order])
m4.metric("B&W", "On" if bw_mode else "Off")

plot_tab, analysis_tab, derivative_tab, quantitative_tab, data_tab, export_tab, help_tab = st.tabs([
    "📈 Spectrum", "🧪 Analysis", "∂ Derivatives", "📐 Quantitative tools", "📋 Data", "💾 Export", "❓ Help"
])

with plot_tab:
    st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False, "scrollZoom": True, "responsive": True})
    st.caption("Hover for exact wavelength and signal. Drag/scroll to zoom; double-click to reset.")
    if bw_mode:
        st.markdown('<div class="pubnote"><b>Monochrome publication mode:</b> all curves are black and distinguished by line style.</div>', unsafe_allow_html=True)

with analysis_tab:
    md = pd.DataFrame(metrics).rename(columns={
        "lambda_max": "λmax (nm)", "y_max": "Signal at λmax", "lambda_min": "λmin (nm)", "y_min": "Signal at λmin",
        "area": "Signed AUC (full range)", "absolute_area": "Absolute AUC (full range)", "centroid": "Centroid (nm)",
        "fwhm": "FWHM (nm)", "peak_count": "Peaks",
    })
    st.markdown("#### Spectral metrics")
    st.dataframe(md, use_container_width=True, hide_index=True)
    st.markdown("#### Detected peaks")
    pdp = pd.DataFrame(all_peak_rows).rename(columns={"wavelength_nm": "Wavelength (nm)", "intensity": "Signal", "prominence": "Prominence", "fwhm_nm": "FWHM (nm)"})
    st.dataframe(pdp, use_container_width=True, hide_index=True) if not pdp.empty else st.info("No peaks met the current prominence criterion.")

with derivative_tab:
    st.markdown("#### Derivative spectroscopy: 0D–4D")
    st.write("Select original, first, second, third or fourth derivative from the sidebar. Uniform grids use Savitzky–Golay differentiation; irregular wavelength grids use coordinate-aware numerical gradients.")
    if derivative_order >= 1:
        st.markdown("#### Zero-crossing wavelengths")
        zdf = pd.DataFrame(zero_rows).rename(columns={"wavelength_nm": "Zero crossing (nm)"})
        st.dataframe(zdf, use_container_width=True, hide_index=True) if not zdf.empty else st.info("No zero crossings detected.")
    if derivative_order >= 3:
        st.warning("High-order derivatives are highly noise-sensitive. Prefer an analytically justified smoothing strategy and report window/order or σ in the methods section.")
    st.markdown("#### Selected-range AUC")
    st.dataframe(pd.DataFrame(auc_rows), use_container_width=True, hide_index=True) if auc_rows else st.info("Enable AUC and choose a valid interval.")

with quantitative_tab:
    st.markdown("#### Signal extraction at selected wavelength")
    wavelength_text = st.text_input("Wavelength(s), nm — comma separated", "270")
    requested = []
    for token in wavelength_text.replace(";", ",").split(","):
        try:
            requested.append(float(token.strip()))
        except ValueError:
            pass
    signal_rows = []
    for s in processed:
        for w in requested:
            signal_rows.append({"Curve": s["name"], "Wavelength (nm)": w, "Signal": signal_at_wavelength(s["x"], s["analysis_y"], w)})
    if signal_rows:
        st.dataframe(pd.DataFrame(signal_rows), use_container_width=True, hide_index=True)

    st.markdown("#### Signal-to-noise estimation")
    q1, q2 = st.columns(2)
    noise_min = q1.number_input("Noise region from (nm)", value=max(xlo, xhi - (xhi-xlo)*0.1))
    noise_max = q2.number_input("Noise region to (nm)", value=xhi)
    snr_rows = []
    for s in processed:
        snr_rows.append({"Curve": s["name"], **estimate_snr(s["x"], s["analysis_y"], noise_min, noise_max)})
    st.dataframe(pd.DataFrame(snr_rows).rename(columns={"noise_sd":"Noise SD", "peak_signal":"Peak signal vs noise mean", "snr":"S/N"}), use_container_width=True, hide_index=True)
    st.caption("S/N here is an exploratory spectral estimate using the standard deviation in the selected noise-only region; use your validated laboratory definition for regulatory reporting.")

with data_tab:
    st.dataframe(merged, use_container_width=True, hide_index=True, height=460)
    st.caption("Processed analytical values; visual offsets are excluded.")

with export_tab:
    st.markdown("#### Publication export")
    e1, e2, e3 = st.columns(3)
    win = e1.number_input("Width (inches)", 2.0, 20.0, 7.0, 0.25)
    hin = e2.number_input("Height (inches)", 2.0, 20.0, 5.0, 0.25)
    dpi = e3.select_slider("PNG resolution", [300, 600, 720, 900, 1200], 600, format_func=lambda x: f"{x} DPI")
    st.info(f"PNG: **{round(win*dpi):,} × {round(hin*dpi):,} pixels** at **{dpi} DPI**. SVG/PDF remain vector formats.")
    d1, d2, d3, d4 = st.columns(4)
    try:
        d1.download_button(f"PNG · {dpi} DPI", figure_png_bytes(fig, win, hin, int(dpi)), "uvvis_spectrum.png", "image/png", use_container_width=True)
    except Exception as exc:
        d1.warning(f"PNG unavailable: {exc}")
    try:
        d2.download_button("SVG", figure_vector_bytes(fig, "svg", win, hin), "uvvis_spectrum.svg", "image/svg+xml", use_container_width=True)
    except Exception:
        d2.button("SVG unavailable", disabled=True, use_container_width=True)
    try:
        d3.download_button("PDF", figure_vector_bytes(fig, "pdf", win, hin), "uvvis_spectrum.pdf", "application/pdf", use_container_width=True)
    except Exception:
        d3.button("PDF unavailable", disabled=True, use_container_width=True)
    d4.download_button("Processed CSV", merged.to_csv(index=False).encode("utf-8-sig"), "uvvis_processed.csv", "text/csv", use_container_width=True)
    if auc_rows:
        st.download_button("AUC table (CSV)", pd.DataFrame(auc_rows).to_csv(index=False).encode("utf-8-sig"), "uvvis_auc.csv", "text/csv")
    if all_peak_rows:
        st.download_button("Peak table (CSV)", pd.DataFrame(all_peak_rows).to_csv(index=False).encode("utf-8-sig"), "uvvis_peaks.csv", "text/csv")
    if zero_rows:
        st.download_button("Zero-crossing table (CSV)", pd.DataFrame(zero_rows).to_csv(index=False).encode("utf-8-sig"), "uvvis_zero_crossings.csv", "text/csv")

with help_tab:
    st.markdown("""#### Main analytical capabilities
- Original spectrum plus **1st, 2nd, 3rd and 4th derivatives**.
- Savitzky–Golay, moving-average and Gaussian smoothing.
- ALS, linear-endpoint and polynomial-edge baseline correction.
- Full-range and selected-range signed/absolute AUC.
- λmax, λmin, centroid, peak count, prominence and FWHM.
- Zero-crossing analysis for derivative spectrophotometry.
- Exact/interpolated signal extraction at specified wavelengths.
- Exploratory signal-to-noise estimation using a user-defined noise region.
- Blank/reference subtraction, difference, ratio and spectral addition.
- Absorbance ↔ %Transmittance conversion.
- Per-curve line style and color, plus black-and-white publication mode.
- PNG 300–1200 DPI, SVG, PDF and processed CSV export.

**Scientific practice:** high-order derivatives, smoothing and baseline correction can change quantitative results. Record all processing parameters and avoid applying preprocessing unless analytically justified.
""")

st.divider()
st.caption("UV-Vis Spectrum Studio · advanced analytical spectroscopy workspace")
