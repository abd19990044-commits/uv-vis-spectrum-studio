from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from .analysis import (
    absorbance_to_transmittance,
    auc_unit,
    auc_unit_angstrom,
    calculate_metrics,
    convert_auc_to_angstrom,
    crop_xy,
    derivative_unit,
    estimate_snr,
    integrate_range,
    peak_table,
    process_spectrum,
    signal_at_wavelength,
    spectral_arithmetic,
    transmittance_to_absorbance,
    zero_crossings,
)
from .chemometrics_ui import render_chemometrics
from .export import figure_png_bytes, figure_vector_bytes
from .io import clean_xy, detect_wavelength_column, numeric_signal_columns, read_table
from .project import load_project, project_bytes
from .quantitation import breusch_pagan_calibration_test, independent_blank_statistics, isosbestic_points, job_method, linear_calibration, mole_ratio_method, standard_addition
from .validation import inverse_prediction_interval, lack_of_fit_test, linearity_validation, mandel_fitting_test
from .transforms import (
    check_grid_uniformity,
    cwt_analysis,
    fft_analysis,
    wavelet_denoise,
    wavelet_denoise_full,
)
from . import __version__
from .workspace_state import capture_settings, clear_project_session, restore_project_to_session

APP_NAME = "UV-Vis Spectrum Studio"
APP_VERSION = __version__
COLORS = ["#2563EB", "#DC2626", "#059669", "#7C3AED", "#EA580C", "#0891B2", "#DB2777", "#475569"]
LINE_STYLES = {"Solid": "solid", "Dashed": "dash", "Dotted": "dot", "Dash-dot": "dashdot", "Long dash": "longdash", "Long dash-dot": "longdashdot"}
BW_STYLES = ["solid", "dash", "dot", "dashdot", "longdash", "longdashdot"]
FONT_FAMILIES = ["Times New Roman", "Arial", "Calibri", "Cambria", "Georgia", "Verdana", "Courier New"]
DERIVATIVE_LABELS = [
    "Original spectrum (0D)",
    "First derivative (1D)",
    "Second derivative (2D)",
    "Third derivative (3D)",
    "Fourth derivative (4D)",
]


def _set_auc_full_range(lo: float, hi: float) -> None:
    st.session_state["auc_min"] = float(lo)
    st.session_state["auc_max"] = float(hi)
    st.session_state["input_auc_min"] = float(lo)
    st.session_state["input_auc_max"] = float(hi)


def _apply_auc_interval() -> None:
    lo = float(st.session_state["input_auc_min"])
    hi = float(st.session_state["input_auc_max"])
    if not np.isfinite([lo, hi]).all() or lo >= hi:
        st.session_state["_auc_error"] = "Start wavelength must be smaller than end wavelength."
        return
    st.session_state.pop("_auc_error", None)
    st.session_state["auc_min"] = lo
    st.session_state["auc_max"] = hi
    st.session_state["shade_auc"] = bool(st.session_state["auc_shade_toggle"])


def get_y_axis_label(order: int = 0, conversion: str = "None", normalization: str = "None") -> str:
    """Determine physically accurate Y-axis label reflecting derivative order and normalization."""
    if normalization == "Area = 1":
        return f"Area-normalized signal ({derivative_unit(order, '1/nm')})"
    if normalization in {"Max = 1", "Min-Max 0–1"}:
        if order == 0:
            return "Normalized Intensity (dimensionless)"
        return f"Normalized Derivative (nm^-{order})"

    base = "%Transmittance (%T)" if conversion == "Absorbance → %Transmittance" else "Absorbance (Abs)"
    short_base = "%T" if conversion == "Absorbance → %Transmittance" else "Abs"

    if order == 0:
        return base
    if order == 1:
        return f"First Derivative d({short_base})/dλ ({short_base}/nm)"
    if order == 2:
        return f"Second Derivative d²({short_base})/dλ² ({short_base}/nm²)"
    if order == 3:
        return f"Third Derivative d³({short_base})/dλ³ ({short_base}/nm³)"
    if order == 4:
        return f"Fourth Derivative d⁴({short_base})/dλ⁴ ({short_base}/nm⁴)"
    return f"d^{order}({short_base})/dλ^{order}"


def _signal_base_unit(conversion: str, normalization: str) -> str:
    if normalization == "Area = 1":
        return "1/nm"
    if normalization in {"Max = 1", "Min-Max 0–1"}:
        return "relative"
    return "%T" if conversion == "Absorbance → %Transmittance" else "Abs"


def safe_filename(name: str, fallback: str = "uvvis_spectrum") -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", str(name)).strip(" .")
    return name or fallback


def choose_directory(initial: str) -> str | None:
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        value = filedialog.askdirectory(initialdir=initial or str(Path.home()))
        root.destroy()
        return value or None
    except Exception:
        return None


def save_bytes(folder: str, filename: str, data: bytes) -> Path:
    outdir = Path(folder).expanduser()
    outdir.mkdir(parents=True, exist_ok=True)
    target = outdir / safe_filename(filename)
    target.write_bytes(data)
    return target


def _init(key: str, value) -> None:
    if key not in st.session_state:
        st.session_state[key] = value


def _load_project_before_widgets() -> None:
    with st.sidebar:
        st.markdown("### Project")
        project_upload = st.file_uploader(
            "Open UV-Vis project",
            type=["uvvisproj", "zip"],
            key="workspace_project_upload",
            help="Restores raw spectra, curve appearance and processing/publication settings.",
        )
        if project_upload is not None:
            raw = project_upload.getvalue()
            token = sha256(raw).hexdigest()
            if st.session_state.get("_loaded_project_token") != token:
                try:
                    project = load_project(raw)
                    restore_project_to_session(st.session_state, project)
                    st.session_state["_loaded_project_token"] = token
                    st.session_state["_project_loaded_message"] = f"Restored {len(project['spectra'])} spectra from {project_upload.name}."
                    st.rerun()
                except Exception as exc:
                    st.error(f"Project could not be opened: {exc}")
        if "_project_loaded_message" in st.session_state:
            st.success(st.session_state.pop("_project_loaded_message"))
        if st.session_state.get("_project_spectra"):
            st.caption(f"Active project: **{st.session_state.get('_project_name', 'Untitled')}** ({len(st.session_state['_project_spectra'])} curves)")
            if st.button("Clear loaded project", key="clear_project_btn", use_container_width=True):
                clear_project_session(st.session_state)
                st.rerun()


def _project_curves() -> list[dict]:
    restored = []
    for spec in st.session_state.get("_project_spectra", []):
        restored.append(
            {
                "name": spec["name"],
                "x": np.asarray(spec["x"], dtype=float),
                "y": np.asarray(spec["y"], dtype=float),
                "raw_y": np.asarray(spec.get("raw_y", spec["y"]), dtype=float),
                "color": spec.get("color", "#2563EB"),
                "dash": spec.get("dash", "solid"),
                "source": spec.get("source", "project"),
                "column": spec.get("column", "signal"),
            }
        )
    return restored


def run() -> None:
    st.set_page_config(
        page_title="UV-Vis Spectrum Studio",
        page_icon="🔬",
        layout="wide",
        initial_sidebar_state="auto",
    )

    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.2rem; padding-bottom: 2.5rem; max-width: 98%; }
        .hero-banner {
            background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
            color: #F8FAFC;
            padding: 1.1rem 1.6rem;
            border-radius: 10px;
            margin-bottom: 1.2rem;
            border-left: 5px solid #2563EB;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        .hero-banner h1 { margin: 0; font-size: 1.75rem; font-weight: 700; color: #FFFFFF; }
        .hero-banner p { margin: 0.25rem 0 0 0; font-size: 0.95rem; color: #94A3B8; }
        .stMetric { background: #F8FAFC; border: 1px solid #E2E8F0; padding: 0.6rem 0.8rem; border-radius: 8px; }
        .card-container { background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="hero-banner">
            <h1>🔬 UV-Vis Spectrum Studio</h1>
            <p>v{APP_VERSION} · Shimadzu LabSolutions-inspired analytical spectroscopy workstation · chemometrics, derivative analysis & publication graphics</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _init("_project_notes", "")
    _load_project_before_widgets()

    with st.sidebar:
        st.markdown("### Spectral Workspace")
        files = st.file_uploader(
            "Load UV–Vis files",
            type=["xlsx", "xls", "xlsm", "csv", "txt", "dat", "asc", "tsv"],
            accept_multiple_files=True,
            key="spectral_files",
        )
        st.caption("Excel, CSV, TSV, TXT, DAT, ASC. Combine project archives with newly ingested files.")

    spectra = _project_curves()
    errors = []
    if files:
        for i, up in enumerate(files):
            try:
                df = read_table(BytesIO(up.getvalue()), up.name)
                cols = [str(c) for c in df.columns]
                try:
                    auto = detect_wavelength_column(df)
                except ValueError:
                    auto = cols[0]
                with st.sidebar.expander(f"Curve setup · {up.name}", expanded=i == 0 and not spectra):
                    xcol = st.selectbox("Wavelength column", cols, index=cols.index(auto), key=f"x{i}")
                    yopts = numeric_signal_columns(df, xcol)
                    ys = st.multiselect("Signal columns", yopts, default=yopts[:1], key=f"y{i}")
                    for j, ycol in enumerate(ys):
                        x, y = clean_xy(df, xcol, ycol)
                        st.caption(f"{len(df)} rows → {len(x)} unique finite wavelength/signal pairs; duplicate wavelengths are averaged.")
                        default_name = Path(up.name).stem if len(ys) == 1 else f"{Path(up.name).stem} · {ycol}"
                        name = st.text_input("Curve display name", value=default_name, key=f"name{i}_{j}")
                        c1, c2 = st.columns(2)
                        color = c1.color_picker("Color", COLORS[len(spectra) % len(COLORS)], key=f"color{i}_{j}")
                        style_name = c2.selectbox("Line style", list(LINE_STYLES), index=0, key=f"style{i}_{j}")
                        spectra.append(
                            {
                                "name": name,
                                "x": x,
                                "y": y,
                                "raw_y": np.asarray(y, dtype=float).copy(),
                                "color": color,
                                "dash": LINE_STYLES[style_name],
                                "source": up.name,
                                "column": ycol,
                            }
                        )
            except Exception as exc:
                errors.append(f"{up.name}: {exc}")
    for err in errors:
        st.error(err)

    if spectra:
        allx = np.concatenate([np.asarray(s["x"], dtype=float) for s in spectra])
        xlo, xhi = float(np.nanmin(allx)), float(np.nanmax(allx))
        bounds = (xlo, xhi)
        if (st.session_state.get("_data_bounds") != bounds
                and not st.session_state.get("_project_spectra")):
            _set_auc_full_range(xlo, xhi)
        st.session_state["_data_bounds"] = bounds
    else:
        xlo, xhi = 200.0, 800.0

    defaults = {
        "view_mode": "Standard Spectrum Viewer",
        "derivative_order": 0,
        "crop": False,
        "xmin": xlo,
        "xmax": xhi,
        "x_auto": True,
        "y_auto": True,
        "ymin_disp": 0.0,
        "ymax_disp": 1.0,
        "smoothing_method": "None",
        "window": 11,
        "poly": 3,
        "gaussian_sigma": 2.0,
        "baseline_method": "None",
        "blam": 1_000_000.0,
        "bp": 0.01,
        "baseline_poly_order": 2,
        "baseline_edge_fraction": 0.10,
        "norm": "None",
        "conversion": "None",
        "auc_enabled": True,
        "auc_min": xlo,
        "auc_max": xhi,
        "shade_auc": True,
        "title": "UV–Vis spectra",
        "xtitle": "Wavelength (nm)",
        "ytitle": "",
        "bw_mode": False,
        "bw_auto": False,
        "font_family": "Times New Roman",
        "linewidth": 2.0,
        "fontsize": 14,
        "titlesize": 18,
        "grid": True,
        "legend": True,
        "legendpos": "Top right",
        "label_peaks": False,
        "peak_prominence_pct": 3.0,
        "peak_distance": 1,
        "offset": 0.0,
    }
    for key, value in defaults.items():
        _init(key, value)

    with st.sidebar:
        st.divider()
        st.markdown("### Spectral Processing")
        derivative_order = st.selectbox(
            "Derivative order",
            range(5),
            format_func=lambda v: DERIVATIVE_LABELS[v],
            key="derivative_order",
        )
        if derivative_order >= 3:
            st.warning("Third/fourth derivatives strongly amplify noise. Apply smoothing with appropriate parameters.")

        crop = st.toggle("Limit wavelength calculation window", key="crop")
        cc1, cc2 = st.columns(2)
        xmin = cc1.number_input("X min (nm)", key="xmin", disabled=not crop)
        xmax = cc2.number_input("X max (nm)", key="xmax", disabled=not crop)

        st.markdown("#### Smoothing (OFF by default)")
        smoothing_method = st.selectbox(
            "Smoothing method",
            ["None", "Savitzky-Golay", "Moving average", "Gaussian"],
            key="smoothing_method",
        )
        window = int(st.session_state["window"])
        poly = int(st.session_state["poly"])
        gaussian_sigma = float(st.session_state["gaussian_sigma"])

        # Display ONLY controls applicable to selected algorithm
        if smoothing_method in {"Savitzky-Golay", "Moving average"}:
            sc1, sc2 = st.columns(2)
            window = sc1.number_input("Window points", 3, 201, step=2, key="window")
            if smoothing_method == "Savitzky-Golay":
                poly = sc2.number_input("Polynomial order", 1, 9, step=1, key="poly")
        elif smoothing_method == "Gaussian":
            gaussian_sigma = st.number_input("Gaussian σ (points)", 0.1, 50.0, step=0.1, key="gaussian_sigma")

        st.markdown("#### Baseline & Normalization")
        baseline_method = st.selectbox(
            "Baseline correction",
            ["None", "ALS", "Linear endpoints", "Polynomial edges"],
            key="baseline_method",
        )
        blam = float(st.session_state["blam"])
        bp = float(st.session_state["bp"])
        baseline_poly_order = int(st.session_state["baseline_poly_order"])
        baseline_edge_fraction = float(st.session_state["baseline_edge_fraction"])
        if baseline_method == "ALS":
            bc1, bc2 = st.columns(2)
            blam = bc1.number_input("ALS λ", 1.0, format="%.0f", key="blam")
            bp = bc2.number_input("ALS p", 0.0001, 0.5, format="%.4f", key="bp")
        elif baseline_method in {"Linear endpoints", "Polynomial edges"}:
            baseline_edge_fraction = st.slider("Edge fraction", 0.02, 0.40, step=0.01, key="baseline_edge_fraction")
            if baseline_method == "Polynomial edges":
                baseline_poly_order = st.number_input("Polynomial order", 1, 5, step=1, key="baseline_poly_order")

        norm = st.selectbox("Normalization", ["None", "Max = 1", "Min-Max 0–1", "Area = 1"], key="norm")
        conversion = st.selectbox("Photometric conversion", ["None", "Absorbance → %Transmittance", "%Transmittance → Absorbance"], key="conversion")

    # Spectral Arithmetic
    if spectra and len(spectra) >= 2:
        with st.sidebar.expander("Spectral Arithmetic (Difference / Ratio / Sum)"):
            arithmetic = st.selectbox("Operation", ["None", "Blank/reference subtraction", "Difference A − B", "Ratio A / B", "Add A + B"])
            if arithmetic != "None":
                names = [s["name"] for s in spectra]
                a_name = st.selectbox("Spectrum A", names, 0)
                b_name = st.selectbox("Spectrum B / Reference", names, min(1, len(names) - 1))
                sa = next(s for s in spectra if s["name"] == a_name)
                sb = next(s for s in spectra if s["name"] == b_name)
                xo, yo = spectral_arithmetic(sa["x"], sa["y"], sb["x"], sb["y"], arithmetic)
                dname = st.text_input("Derived curve name", f"{a_name} · {arithmetic} · {b_name}")
                spectra.append({"name": dname, "x": xo, "y": yo, "raw_y": np.asarray(yo, dtype=float).copy(), "color": "#111827", "dash": "solid", "source": "Derived", "column": arithmetic})

    # Spectrum processing loop
    processed = []
    for idx, s in enumerate(spectra):
        x, y = crop_xy(s["x"], s["y"], xmin if crop else None, xmax if crop else None)
        if len(x) < 2:
            continue
        if conversion == "Absorbance → %Transmittance":
            y = absorbance_to_transmittance(y)
        elif conversion == "%Transmittance → Absorbance":
            y = transmittance_to_absorbance(y)
        if not np.all(np.isfinite(y)):
            st.error(f"{s['name']}: photometric conversion produced undefined values. Check for zero/negative transmittance or extreme absorbance.")
            continue

        # Precompute all derivative representations (0D through 4D) for instant switching and multi-curve analysis
        deriv_dict = {}
        for order_k in range(5):
            xk, yk = process_spectrum(
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
                derivative_order=order_k,
            )
            deriv_dict[order_k] = yk

        offset_val = float(st.session_state.get("offset", 0.0))
        yp = deriv_dict[int(derivative_order)]
        processed.append({
            **s,
            "x": x,
            "analysis_y": yp,
            "plot_y": yp + idx * offset_val,
            "orig_x": x,
            "orig_y": deriv_dict[0],
            "derivatives": deriv_dict,
        })

    # Wavelength bounds across processed curves
    if processed:
        all_px = np.concatenate([s["x"] for s in processed])
        pxlo, pxhi = float(np.nanmin(all_px)), float(np.nanmax(all_px))
    else:
        pxlo, pxhi = xlo, xhi

    # Primary tabs
    tabs = st.tabs([
        "📈 Spectra",
        "∂ Derivatives & AUC",
        "〰 FFT / Wavelet",
        "📏 Calibration",
        "🧪 Stoichiometry",
        "➕ Standard addition",
        "🧮 Chemometrics",
        "📊 Data & metrics",
        "💾 Project & export",
    ])

    # -------------------------------------------------------------------------
    # TAB 0: SHIMADZU LABSOLUTIONS-INSPIRED SPECTRUM WORKSTATION
    # -------------------------------------------------------------------------
    with tabs[0]:
        if not processed:
            st.info("Load one or more UV-Vis spectra from the sidebar to activate the analytical workstation.")
        else:
            # Top Ribbon: Analytical Mode & Quick Toolbar
            r1, r2 = st.columns([3, 2])
            with r1:
                view_mode = st.radio(
                    "Workstation Mode",
                    [
                        "Standard Spectrum Viewer",
                        "Derivative Comparison (0D vs nD)",
                        "Selected-Range AUC Inspection",
                        "Multi-Spectrum Overlay",
                    ],
                    horizontal=True,
                    key="view_mode_selector",
                )
            with r2:
                tc1, tc2, tc3, tc4 = st.columns(4)
                label_peaks = tc1.checkbox("Peak λmax", value=st.session_state.get("label_peaks", False), key="lab_label_peaks")
                grid = tc2.checkbox("Gridlines", value=st.session_state.get("grid", True), key="lab_grid")
                legend = tc3.checkbox("Legend", value=st.session_state.get("legend", True), key="lab_legend")
                bw_mode = tc4.checkbox("B&W Mode", value=st.session_state.get("bw_mode", False), key="lab_bw_mode")
                for setting, value in (("label_peaks", label_peaks), ("grid", grid),
                                       ("legend", legend), ("bw_mode", bw_mode)):
                    st.session_state[setting] = value

            # AUC inputs in sidebar/session_state
            auc_min = float(st.session_state.get("auc_min", pxlo))
            auc_max = float(st.session_state.get("auc_max", pxhi))
            auc_enabled = st.session_state.get("auc_enabled", True)
            shade_auc = st.session_state.get("shade_auc", True)

            # Axis customization values
            auto_ytitle = get_y_axis_label(derivative_order, conversion, norm)
            user_ytitle = st.session_state.get("ytitle", "")
            final_ytitle = user_ytitle.strip() if user_ytitle.strip() else auto_ytitle
            final_xtitle = st.session_state.get("xtitle", "Wavelength (nm)")
            title_text = st.session_state.get("title", "UV–Vis spectra")
            font_fam = st.session_state.get("font_family", "Times New Roman")
            font_sz = int(st.session_state.get("fontsize", 14))
            title_sz = int(st.session_state.get("titlesize", 18))
            line_w = float(st.session_state.get("linewidth", 2.0))
            legend_pos = st.session_state.get("legendpos", "Top right")
            peak_prom_pct = float(st.session_state.get("peak_prominence_pct", 3.0))
            peak_dist = int(st.session_state.get("peak_distance", 1))

            pos_map = {
                "Top right": dict(x=.99, y=.99, xanchor="right", yanchor="top"),
                "Top left": dict(x=.01, y=.99, xanchor="left", yanchor="top"),
                "Bottom right": dict(x=.99, y=.01, xanchor="right", yanchor="bottom"),
                "Bottom left": dict(x=.01, y=.01, xanchor="left", yanchor="bottom"),
                "Outside right": dict(x=1.02, y=1, xanchor="left", yanchor="top"),
            }

            # Build Hero Figure
            auc_rows = []
            peak_rows = []
            zero_rows = []
            metrics = []

            if view_mode == "Derivative Comparison (0D vs nD)":
                is_compare_mode = True
                d_c1, d_c2 = st.columns([2, 3])
                with d_c1:
                    comp_order = st.selectbox(
                        "Comparison Derivative Order",
                        [1, 2, 3, 4],
                        index=int(max(1, min(4, derivative_order if derivative_order > 0 else 1))) - 1,
                        format_func=lambda v: DERIVATIVE_LABELS[v],
                        key="tab0_comp_order_select",
                    )
                with d_c2:
                    comp_unit = derivative_unit(comp_order, _signal_base_unit(conversion, norm))
                    st.info(f"Comparing **0D Original** vs **{comp_order}D Derivative ({comp_unit})** across {len(processed)} curve(s).")
            else:
                is_compare_mode = False
                comp_order = int(derivative_order)

            if is_compare_mode:
                comp_unit = derivative_unit(comp_order, _signal_base_unit(conversion, norm))
                fig = make_subplots(
                    rows=2,
                    cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.08,
                    subplot_titles=["Original Spectrum (0D)", f"Derivative Spectrum ({comp_order}D) — {comp_unit}"],
                )
                for idx, s in enumerate(processed):
                    col = "#000000" if bw_mode else s["color"]
                    # Top subplot: 0D
                    fig.add_trace(
                        go.Scatter(
                            x=s["orig_x"],
                            y=s["orig_y"],
                            mode="lines",
                            name=f"{s['name']} (0D)",
                            line=dict(color=col, width=line_w),
                            hovertemplate="<b>0D: %{fullData.name}</b><br>λ=%{x:.2f} nm<br>Signal=%{y:.6g}<extra></extra>",
                        ),
                        row=1,
                        col=1,
                    )
                    # Bottom subplot: comp_order derivative
                    y_d = s["derivatives"][comp_order]
                    fig.add_trace(
                        go.Scatter(
                            x=s["x"],
                            y=y_d + idx * offset_val,
                            mode="lines",
                            name=f"{s['name']} ({comp_order}D)",
                            line=dict(color=col, width=line_w, dash="solid"),
                            hovertemplate=f"<b>{comp_order}D: %{{fullData.name}}</b><br>λ=%{{x:.2f}} nm<br>Derivative=%{{y:.6g}}<extra></extra>",
                        ),
                        row=2,
                        col=1,
                    )
                    # Zero crossings on derivative
                    zc = zero_crossings(s["x"], y_d)
                    zero_rows.extend([{"Curve": s["name"], **z} for z in zc])
                    if zc:
                        fig.add_trace(
                            go.Scatter(
                                x=[z["wavelength_nm"] for z in zc],
                                y=[0.0] * len(zc),
                                mode="markers",
                                marker=dict(symbol="x", size=8, color="#DC2626"),
                                name=f"Zero crossings ({s['name']})",
                                showlegend=False,
                            ),
                            row=2,
                            col=1,
                        )
                fig.update_xaxes(title_text=final_xtitle, row=2, col=1)
                fig.update_yaxes(title_text="Absorbance (0D)", row=1, col=1)
                fig.update_yaxes(title_text=get_y_axis_label(comp_order, conversion, norm), row=2, col=1)
            else:
                fig = go.Figure()
                for idx, s in enumerate(processed):
                    dash = BW_STYLES[idx % len(BW_STYLES)] if (bw_mode and st.session_state.get("bw_auto", False)) else s["dash"]
                    col = "#000000" if bw_mode else s["color"]
                    fig.add_trace(
                        go.Scatter(
                            x=s["x"],
                            y=s["plot_y"],
                            mode="lines",
                            name=s["name"],
                            line=dict(color=col, width=line_w, dash=dash),
                            hovertemplate=f"<b>{s['name']}</b><br>λ=%{{x:.2f}} nm<br>Signal=%{{y:.6g}}<extra></extra>",
                        )
                    )
                    yrange = float(np.nanmax(s["analysis_y"]) - np.nanmin(s["analysis_y"])) if len(s["analysis_y"]) else 1.0
                    prom = max(yrange * peak_prom_pct / 100.0, np.finfo(float).eps)
                    peaks = peak_table(s["x"], s["analysis_y"], prominence=prom, distance=peak_dist)
                    peak_rows.extend([{"Curve": s["name"], **p} for p in peaks])
                    if label_peaks and peaks:
                        fig.add_trace(
                            go.Scatter(
                                x=[p["wavelength_nm"] for p in peaks],
                                y=[signal_at_wavelength(s["x"], s["plot_y"], p["wavelength_nm"]) for p in peaks],
                                mode="markers+text",
                                marker=dict(size=7, color=col),
                                text=[f"{p['wavelength_nm']:.1f} nm" for p in peaks],
                                textposition="top center",
                                showlegend=False,
                                hoverinfo="skip",
                            )
                        )

                    # Selected-range AUC integration
                    if auc_enabled or view_mode == "Selected-Range AUC Inspection":
                        signed_auc, absolute_auc, xa, ya = integrate_range(s["x"], s["analysis_y"], auc_min, auc_max)
                        if len(xa) >= 2:
                            base_unit = _signal_base_unit(conversion, norm)
                            s_auc_a, a_auc_a, _ = convert_auc_to_angstrom(signed_auc, absolute_auc, base_unit=base_unit)
                            unit_str = auc_unit(derivative_order, base_unit)
                            angstrom_unit = auc_unit_angstrom(derivative_order, base_unit)
                            auc_rows.append({
                                "Curve": s["name"],
                                "From (nm)": float(xa[0]),
                                "To (nm)": float(xa[-1]),
                                "From (Å)": float(xa[0] * 10.0),
                                "To (Å)": float(xa[-1] * 10.0),
                                f"Signed AUC ({angstrom_unit})": s_auc_a,
                                f"Absolute AUC ({angstrom_unit})": a_auc_a,
                                f"Signed AUC ({unit_str})": signed_auc,
                                f"Absolute AUC ({unit_str})": absolute_auc,
                            })
                            if shade_auc:
                                # Highlight shaded region
                                fill_c = "rgba(80,80,80,0.15)" if bw_mode else "rgba(37,99,235,0.18)"
                                fig.add_trace(
                                    go.Scatter(
                                        x=xa,
                                        y=ya + idx * offset_val,
                                        fill="tozeroy",
                                        mode="lines",
                                        line=dict(color="rgba(37,99,235,0.4)", width=1),
                                        fillcolor=fill_c,
                                        name=f"AUC [{xa[0]:.1f}–{xa[-1]:.1f} nm / {xa[0]*10:.0f}–{xa[-1]*10:.0f} Å]",
                                        showlegend=(idx == 0),
                                        hoverinfo="skip",
                                    )
                                )

                    metrics.append({"Curve": s["name"], **asdict(calculate_metrics(s["x"], s["analysis_y"], prominence=prom))})
                    if derivative_order > 0:
                        zero_rows.extend([{"Curve": s["name"], **z} for z in zero_crossings(s["x"], s["analysis_y"], tolerance=max(yrange * 1e-8, 0))])

                # Vertical boundary markers for AUC region
                if (auc_enabled or view_mode == "Selected-Range AUC Inspection") and shade_auc and auc_min < auc_max:
                    fig.add_vline(x=auc_min, line_dash="dash", line_color="#DC2626", opacity=0.7)
                    fig.add_vline(x=auc_max, line_dash="dash", line_color="#DC2626", opacity=0.7)

                fig.update_layout(
                    title=dict(text=title_text, font=dict(size=title_sz, family=font_fam), x=0.5, xanchor="center"),
                    xaxis_title=final_xtitle,
                    yaxis_title=final_ytitle,
                    font=dict(size=font_sz, family=font_fam, color="#000"),
                    template="plotly_white",
                    showlegend=legend,
                    legend=pos_map.get(legend_pos, pos_map["Top right"]),
                    hovermode="closest",
                    margin=dict(l=80, r=145 if legend_pos == "Outside right" else 35, t=75, b=70),
                    paper_bgcolor="white",
                    plot_bgcolor="white",
                )

            # Apply user-customized X and Y axis bounds (LabSolutions controls)
            x_auto = st.session_state.get("x_auto", True)
            y_auto = st.session_state.get("y_auto", True)
            if not x_auto:
                xmin_d = float(st.session_state.get("xmin_disp", pxlo))
                xmax_d = float(st.session_state.get("xmax_disp", pxhi))
                if not is_compare_mode:
                    fig.update_xaxes(range=[xmin_d, xmax_d])
                else:
                    fig.update_xaxes(range=[xmin_d, xmax_d], row=1, col=1)
                    fig.update_xaxes(range=[xmin_d, xmax_d], row=2, col=1)

            if not y_auto and not is_compare_mode:
                ymin_d = float(st.session_state.get("ymin_disp", 0.0))
                ymax_d = float(st.session_state.get("ymax_disp", 1.0))
                fig.update_yaxes(range=[ymin_d, ymax_d])

            fig.update_xaxes(
                showgrid=grid,
                mirror=True,
                ticks="outside",
                showline=True,
                linecolor="#111827",
                showspikes=True,
                spikemode="across",
                spikesnap="cursor",
            )
            fig.update_yaxes(
                showgrid=grid,
                mirror=True,
                ticks="outside",
                showline=True,
                linecolor="#111827",
                showspikes=True,
                spikemode="across",
                spikesnap="cursor",
            )

            # RENDER HERO PLOT
            st.plotly_chart(fig, use_container_width=True, config={
                "displaylogo": False,
                "scrollZoom": True,
                "responsive": True,
                "toImageButtonOptions": {
                    "format": "png",
                    "filename": "uvvis_spectrum_labsolutions",
                    "height": 900,
                    "width": 1400,
                    "scale": 2,
                },
            })

            # -----------------------------------------------------------------
            # SECTION: USER-DEFINED WAVELENGTH-RANGE AUC (MANDATORY SECTION)
            # -----------------------------------------------------------------
            st.markdown("### ∬ Area Under the Curve — Selected Wavelength Range")
            st.caption("Integrate within a selected wavelength interval (1 nm = 10 Å). Boundary values are interpolated; intervals crossing zero are split for absolute area. A wavelength integral is independent of cuvette cross-sectional area.")

            ac1, ac2, ac3, ac4, ac5 = st.columns([2, 2, 2, 2, 2])
            with ac1:
                cur_min = float(st.session_state.get("auc_min", pxlo))
                new_min = st.number_input("Start wavelength (nm)", value=cur_min, step=1.0, format="%.2f", key="input_auc_min")
            with ac2:
                cur_max = float(st.session_state.get("auc_max", pxhi))
                new_max = st.number_input("End wavelength (nm)", value=cur_max, step=1.0, format="%.2f", key="input_auc_max")
            with ac3:
                selected_curve_name = st.selectbox("Active curve for interval", ["All curves"] + [s["name"] for s in processed], key="auc_curve_target")
            with ac4:
                auc_unit_choice = st.selectbox("AUC wavelength unit", ["nm", "Å"], index=0, key="auc_unit_select")
            with ac5:
                shade_toggle = st.toggle("Shade integrated area on plot", value=shade_auc, key="auc_shade_toggle")
            st.caption("Press Calculate AUC to apply the entered interval to the plot and results.")
            if st.session_state.get("_auc_error"):
                st.error(st.session_state["_auc_error"])

            # Action Buttons Row
            b1, b2, b3, b4 = st.columns(4)
            b1.button("Set Full Spectrum Range", use_container_width=True,
                      on_click=_set_auc_full_range, args=(pxlo, pxhi))
            b2.button("Reset Range", use_container_width=True,
                      on_click=_set_auc_full_range, args=(pxlo, pxhi))
            b3.button("Calculate AUC", type="primary", use_container_width=True,
                      on_click=_apply_auc_interval)

            # Results use the interval applied to the plot, not uncommitted
            # widget values from this rerun.
            target_spectrum = processed[0] if selected_curve_name == "All curves" else next((s for s in processed if s["name"] == selected_curve_name), processed[0])
            s_auc, a_auc, xx_auc, yy_auc = integrate_range(target_spectrum["x"], target_spectrum["analysis_y"], auc_min, auc_max)
            base_unit = _signal_base_unit(conversion, norm)
            s_auc_a, a_auc_a, _ = convert_auc_to_angstrom(s_auc, a_auc, base_unit=base_unit)
            curr_unit = auc_unit(derivative_order, base_unit)
            angstrom_unit = auc_unit_angstrom(derivative_order, base_unit)
            if len(xx_auc) < 2:
                st.warning("The applied interval contains no spectral data.")
            elif xx_auc[0] != auc_min or xx_auc[-1] != auc_max:
                st.caption(f"Data coverage limits integration to {xx_auc[0]:g}–{xx_auc[-1]:g} nm for the active curve.")

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Selected Interval", f"{auc_min:.2f} – {auc_max:.2f} nm", f"{auc_min*10:.1f} – {auc_max*10:.1f} Å")
            if auc_unit_choice == "Å":
                m2.metric(f"Signed AUC ({angstrom_unit})", f"{s_auc_a:.6g}", f"{s_auc:.5g} {curr_unit}")
                m3.metric(f"Absolute AUC ({angstrom_unit})", f"{a_auc_a:.6g}", f"{a_auc:.5g} {curr_unit}")
                m4.metric("Physical Unit", angstrom_unit)
            else:
                m2.metric(f"Signed AUC ({curr_unit})", f"{s_auc:.6g}", f"{s_auc_a:.5g} {angstrom_unit}")
                m3.metric(f"Absolute AUC ({curr_unit})", f"{a_auc:.6g}", f"{a_auc_a:.5g} {angstrom_unit}")
                m4.metric("Physical Unit", f"{curr_unit}")

            if auc_rows:
                st.dataframe(pd.DataFrame(auc_rows), use_container_width=True, hide_index=True)

            # Export Selected Region Data Action
            if len(xx_auc) >= 2:
                region_df = pd.DataFrame({
                    "Wavelength_nm": xx_auc,
                    "Wavelength_Angstrom": xx_auc * 10.0,
                    "Signal": yy_auc,
                })
                csv_bytes = region_df.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    label=f"📥 Download Selected-Region Data ({float(new_min):.1f}–{float(new_max):.1f} nm / {float(new_min)*10:.0f}–{float(new_max)*10:.0f} Å CSV)",
                    data=csv_bytes,
                    file_name=f"auc_region_{auc_min:.1f}_{auc_max:.1f}nm.csv",
                    mime="text/csv",
                )

            st.divider()

            # -----------------------------------------------------------------
            # SECTION: LABSOLUTIONS-INSPIRED DISPLAY & AXIS CONTROLS
            # -----------------------------------------------------------------
            st.markdown("### 🎛️ Instrument Display & Axis Settings (LabSolutions Controls)")
            c_tab_x, c_tab_y, c_tab_style, c_tab_export = st.tabs([
                "Horizontal (X-Axis)",
                "Vertical (Y-Axis)",
                "Traces & Palette",
                "Publication Export",
            ])

            with c_tab_x:
                xc1, xc2, xc3, xc4 = st.columns(4)
                x_auto_toggle = xc1.toggle("Auto X-axis range", value=st.session_state.get("x_auto", True), key="x_auto")
                xmin_input = xc2.number_input("X minimum (nm)", value=pxlo, key="xmin_disp", disabled=x_auto_toggle)
                xmax_input = xc3.number_input("X maximum (nm)", value=pxhi, key="xmax_disp", disabled=x_auto_toggle)
                xtitle_input = xc4.text_input("X-axis title", value=final_xtitle, key="xtitle")

            with c_tab_y:
                yc1, yc2, yc3, yc4 = st.columns(4)
                y_auto_toggle = yc1.toggle("Auto Y-axis scaling", value=st.session_state.get("y_auto", True), key="y_auto")
                ymin_input = yc2.number_input("Y minimum", value=0.0, key="ymin_disp", disabled=y_auto_toggle)
                ymax_input = yc3.number_input("Y maximum", value=1.0, key="ymax_disp", disabled=y_auto_toggle)
                ytitle_input = yc4.text_input("Y-axis title", key="ytitle", placeholder=auto_ytitle,
                    help="Leave blank to update the axis title automatically with processing units.")
                st.caption(f"Suggested physical unit for current mode: **{auto_ytitle}**")

            with c_tab_style:
                st1, st2, st3, st4 = st.columns(4)
                st1.slider("Line width (pt)", 0.5, 6.0, step=0.5, key="linewidth")
                st2.selectbox("Font family", FONT_FAMILIES, key="font_family")
                st3.slider("Font size", 8, 24, key="fontsize")
                st4.selectbox("Legend position", list(pos_map.keys()), key="legendpos")

            with c_tab_export:
                ep1, ep2, ep3 = st.columns(3)
                win = ep1.number_input("Figure width (in)", 2.0, 20.0, 7.0, 0.5, key="pub_fig_w")
                hin = ep2.number_input("Figure height (in)", 2.0, 20.0, 5.0, 0.5, key="pub_fig_h")
                dpi = ep3.select_slider("Raster DPI", [150, 300, 600, 1200], 300, key="pub_fig_dpi")
                figure_signature = sha256(
                    (fig.to_json() + f"|{win}|{hin}|{dpi}").encode("utf-8")
                ).hexdigest()
                if st.session_state.get("_pub_fig_signature") != figure_signature:
                    st.session_state["_pub_fig_ready"] = False

                if st.button("Generate Publication Figures (PNG/SVG/PDF)", type="primary", use_container_width=True, key="gen_pub_fig_btn"):
                    with st.spinner(f"Rendering publication figures at {dpi} DPI (PNG, SVG, PDF)..."):
                        try:
                            st.session_state["_pub_fig_png"] = figure_png_bytes(fig, win, hin, int(dpi))
                            st.session_state["_pub_fig_png_dpi"] = int(dpi)
                        except Exception as exc:
                            st.session_state["_pub_fig_png"] = None
                            st.error(f"PNG generation error: {exc}")
                        try:
                            st.session_state["_pub_fig_svg"] = figure_vector_bytes(fig, "svg", win, hin)
                        except Exception as exc:
                            st.session_state["_pub_fig_svg"] = None
                            st.caption(f"SVG note: {exc}")
                        try:
                            st.session_state["_pub_fig_pdf"] = figure_vector_bytes(fig, "pdf", win, hin)
                        except Exception as exc:
                            st.session_state["_pub_fig_pdf"] = None
                            st.caption(f"PDF note: {exc}")
                        try:
                            st.session_state["_pub_fig_html"] = fig.to_html(include_plotlyjs="cdn").encode("utf-8")
                        except Exception:
                            st.session_state["_pub_fig_html"] = None
                        st.session_state["_pub_fig_ready"] = True
                        st.session_state["_pub_fig_signature"] = figure_signature

                if st.session_state.get("_pub_fig_ready", False):
                    png_data = st.session_state.get("_pub_fig_png")
                    svg_data = st.session_state.get("_pub_fig_svg")
                    pdf_data = st.session_state.get("_pub_fig_pdf")
                    html_data = st.session_state.get("_pub_fig_html")
                    cached_dpi = st.session_state.get("_pub_fig_png_dpi", dpi)
                    b_png, b_svg, b_pdf, b_html = st.columns(4)
                    if png_data:
                        b_png.download_button(f"📥 Download PNG ({cached_dpi} DPI)", png_data, "uvvis_spectrum_labsolutions.png", "image/png", use_container_width=True)
                    if svg_data:
                        b_svg.download_button("📥 Download SVG (Vector)", svg_data, "uvvis_spectrum_labsolutions.svg", "image/svg+xml", use_container_width=True)
                    if pdf_data:
                        b_pdf.download_button("📥 Download PDF (Vector)", pdf_data, "uvvis_spectrum_labsolutions.pdf", "application/pdf", use_container_width=True)
                    if html_data:
                        b_html.download_button("📥 Download HTML (Interactive)", html_data, "uvvis_spectrum_interactive.html", "text/html", use_container_width=True)
                    st.caption("💡 Tip: You can also hover over the spectrum chart and click the **Camera icon** in the top-right toolbar to instantly save a high-resolution PNG directly from your browser.")
                else:
                    st.info("Click 'Generate Publication Figures' to render high-resolution raster and vector exports. Or hover over the chart and click the camera icon to save instantly.")

            # Isosbestic point analysis
            if len(processed) >= 2:
                st.divider()
                st.markdown("#### Isosbestic-Point Analysis")
                names = [s["name"] for s in processed]
                ic1, ic2 = st.columns(2)
                ia = ic1.selectbox("Spectrum 1", names, 0, key="iso_a")
                ib = ic2.selectbox("Spectrum 2", names, min(1, len(names) - 1), key="iso_b")
                sa_c = next(s for s in processed if s["name"] == ia)
                sb_c = next(s for s in processed if s["name"] == ib)
                pts = isosbestic_points(sa_c["x"], sa_c["analysis_y"], sb_c["x"], sb_c["analysis_y"])
                if pts:
                    st.dataframe(pd.DataFrame(pts).rename(columns={"wavelength_nm": "Wavelength (nm)", "signal": "Signal"}), use_container_width=True, hide_index=True)
                else:
                    st.info("No interpolated crossing detected in common wavelength range.")

    # -------------------------------------------------------------------------
    # TAB 1: DERIVATIVE SPECTROSCOPY (0D THROUGH 4D)
    # -------------------------------------------------------------------------
    with tabs[1]:
        st.markdown("### Derivative Spectroscopy (0D through 4D)")
        st.caption("Inspect and export zero- through fourth-order numerical derivative spectra computed with respect to wavelength (nm).")

        d_col1, d_col2 = st.columns([3, 1])
        with d_col1:
            d_order = st.selectbox(
                "Active Derivative Order",
                range(5),
                index=int(derivative_order),
                format_func=lambda v: DERIVATIVE_LABELS[v],
                key="tab1_derivative_order",
            )
        with d_col2:
            d_unit = derivative_unit(d_order, _signal_base_unit(conversion, norm))
            st.metric("Derivative Unit", d_unit)

        if d_order >= 3:
            st.warning("Higher-order derivatives (3D/4D) amplify experimental high-frequency noise. Apply Savitzky-Golay filtering in the sidebar when appropriate.")

        if processed:
            curve_names = [s["name"] for s in processed]
            sc1, sc2, sc3 = st.columns([3, 2, 2])
            with sc1:
                selected_curves = st.multiselect(
                    "Select spectra to plot and differentiate together",
                    curve_names,
                    default=curve_names,
                    key="tab1_multi_curves",
                    help="Choose one, multiple, or all loaded spectra to differentiate and plot simultaneously.",
                )
            with sc2:
                deriv_layout = st.selectbox(
                    "Visualization Layout",
                    [
                        "Dual Subplot (0D vs nD Comparison)",
                        "Combined nD Derivative Overlay",
                        "Individual Focused Inspection",
                    ],
                    key="tab1_layout_sel",
                )
            with sc3:
                st.write("")
                st.write("")
                b_all, b_first = st.columns(2)
                if b_all.button("Select All", key="tab1_sel_all", use_container_width=True):
                    st.session_state["tab1_multi_curves"] = curve_names
                    st.rerun()
                if b_first.button("First Only", key="tab1_sel_one", use_container_width=True):
                    st.session_state["tab1_multi_curves"] = [curve_names[0]]
                    st.rerun()

            active_names = selected_curves if selected_curves else [curve_names[0]]
            active_specs = [s for s in processed if s["name"] in active_names]

            if deriv_layout == "Dual Subplot (0D vs nD Comparison)":
                d_fig = make_subplots(
                    rows=2,
                    cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.08,
                    subplot_titles=["Original Spectra (0D)", f"Derivative Spectra ({d_order}D) — {d_unit}"],
                )
                for idx, s in enumerate(active_specs):
                    col = s.get("color", COLORS[idx % len(COLORS)])
                    y_d = s["derivatives"][d_order]
                    d_fig.add_trace(
                        go.Scatter(x=s["orig_x"], y=s["orig_y"], name=f"{s['name']} (0D)", line=dict(color=col, width=2)),
                        row=1,
                        col=1,
                    )
                    d_fig.add_trace(
                        go.Scatter(x=s["x"], y=y_d, name=f"{s['name']} ({d_order}D)", line=dict(color=col, width=2)),
                        row=2,
                        col=1,
                    )
                d_fig.update_xaxes(title_text="Wavelength (nm)", row=2, col=1)
                d_fig.update_yaxes(title_text="Absorbance (0D)", row=1, col=1)
                d_fig.update_yaxes(title_text=f"Signal ({d_unit})", row=2, col=1)
                d_fig.update_layout(template="plotly_white", height=600, margin=dict(t=50, b=50, l=70, r=30), hovermode="x unified")
                st.plotly_chart(d_fig, use_container_width=True, config={"displaylogo": False, "scrollZoom": True, "toImageButtonOptions": {"format": "png", "filename": f"derivative_{d_order}D_dual_comparison", "height": 800, "width": 1200, "scale": 2}})

            elif deriv_layout == "Combined nD Derivative Overlay":
                d_fig = go.Figure()
                for idx, s in enumerate(active_specs):
                    col = s.get("color", COLORS[idx % len(COLORS)])
                    y_d = s["derivatives"][d_order]
                    d_fig.add_trace(
                        go.Scatter(x=s["x"], y=y_d, name=f"{s['name']} ({d_order}D)", line=dict(color=col, width=2))
                    )
                if d_order > 0:
                    d_fig.add_hline(y=0.0, line_dash="dash", line_color="#94A3B8", opacity=0.7)
                d_fig.update_layout(
                    title=dict(text=f"Overlay of {d_order}D Derivative Spectra ({len(active_specs)} Curves)", x=0.5, xanchor="center"),
                    xaxis_title="Wavelength (nm)",
                    yaxis_title=f"Derivative Signal ({d_unit})",
                    template="plotly_white",
                    height=520,
                    margin=dict(t=60, b=50, l=70, r=30),
                    hovermode="x unified",
                )
                st.plotly_chart(d_fig, use_container_width=True, config={"displaylogo": False, "scrollZoom": True, "toImageButtonOptions": {"format": "png", "filename": f"derivative_{d_order}D_overlay", "height": 800, "width": 1200, "scale": 2}})

            else:  # Individual Focused Inspection
                focus_name = st.selectbox("Focus Spectrum", active_names, key="tab1_focus_spec")
                focus_s = next(s for s in active_specs if s["name"] == focus_name)
                y_d = focus_s["derivatives"][d_order]
                d_fig = make_subplots(
                    rows=2,
                    cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.08,
                    subplot_titles=[f"{focus_s['name']} — Original (0D)", f"{focus_s['name']} — Derivative ({d_order}D) — {d_unit}"],
                )
                d_fig.add_trace(go.Scatter(x=focus_s["orig_x"], y=focus_s["orig_y"], name="0D Original", line=dict(color="#2563EB", width=2)), row=1, col=1)
                d_fig.add_trace(go.Scatter(x=focus_s["x"], y=y_d, name=f"{d_order}D Derivative", line=dict(color="#DC2626", width=2)), row=2, col=1)
                zc_focus = zero_crossings(focus_s["x"], y_d) if d_order > 0 else []
                if zc_focus:
                    d_fig.add_trace(
                        go.Scatter(
                            x=[z["wavelength_nm"] for z in zc_focus],
                            y=[0.0] * len(zc_focus),
                            mode="markers",
                            marker=dict(symbol="x", size=8, color="#DC2626"),
                            name="Zero crossings",
                        ),
                        row=2,
                        col=1,
                    )
                d_fig.update_xaxes(title_text="Wavelength (nm)", row=2, col=1)
                d_fig.update_yaxes(title_text="Absorbance (0D)", row=1, col=1)
                d_fig.update_yaxes(title_text=f"Signal ({d_unit})", row=2, col=1)
                d_fig.update_layout(template="plotly_white", height=550, margin=dict(t=50, b=50, l=70, r=30))
                st.plotly_chart(d_fig, use_container_width=True, config={"displaylogo": False, "scrollZoom": True, "toImageButtonOptions": {"format": "png", "filename": f"derivative_{d_order}D_{focus_s['name']}", "height": 800, "width": 1200, "scale": 2}})

            # Zero-crossings table for all active curves
            if d_order > 0:
                all_zc = []
                for s in active_specs:
                    y_d = s["derivatives"][d_order]
                    zc = zero_crossings(s["x"], y_d)
                    for z in zc:
                        all_zc.append({"Curve": s["name"], "Zero Crossing Wavelength (nm)": z["wavelength_nm"]})
                st.markdown(f"#### Detected Zero Crossings ({d_order}D)")
                if all_zc:
                    st.dataframe(pd.DataFrame(all_zc), use_container_width=True, hide_index=True)
                else:
                    st.info(f"No zero crossings detected for {d_order}D within current dynamic threshold.")

            # Multi-Curve Derivative Data Export
            ref_x = active_specs[0]["x"]
            export_df_data = {"Wavelength_nm": ref_x}
            for s in active_specs:
                y_d = s["derivatives"][d_order]
                if len(s["x"]) == len(ref_x) and np.allclose(s["x"], ref_x):
                    export_df_data[f"{s['name']}_{d_order}D_{d_unit}"] = y_d
                else:
                    export_df_data[f"{s['name']}_{d_order}D_{d_unit}"] = np.interp(ref_x, s["x"], y_d)
            d_out = pd.DataFrame(export_df_data)
            st.download_button(
                label=f"📥 Download {d_order}D Derivative Data for {len(active_specs)} Selected Curve(s) (CSV)",
                data=d_out.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"derivative_{d_order}D_spectra.csv",
                mime="text/csv",
            )
        else:
            st.info("Load spectra to inspect derivative representations.")

    # -------------------------------------------------------------------------
    # TAB 2: FOURIER & WAVELET TRANSFORMS (FFT, DWT, CWT)
    # -------------------------------------------------------------------------
    with tabs[2]:
        if not processed:
            st.info("Load a spectrum to use Fourier and wavelet analysis.")
        else:
            names = [s["name"] for s in processed]
            target_name = st.selectbox("Target spectrum for transform analysis", names, key="transform_curve")
            target = next(s for s in processed if s["name"] == target_name)

            subtab_fft, subtab_wavelet = st.tabs(["〰 Fourier Transform (FFT)", "🌊 Wavelet Analysis (DWT & CWT)"])

            # SUBTAB A: FFT
            with subtab_fft:
                st.markdown("#### Fourier Transform Analysis")
                grid_diag = check_grid_uniformity(target["x"])
                if grid_diag["is_uniform"]:
                    st.success(f"Wavelength grid is uniform: Δλ = {grid_diag['median_dx']:.4f} nm ({grid_diag['n_points']} points).")
                else:
                    st.warning(
                        f"Nonuniform wavelength grid detected (relative spread: {grid_diag['relative_spread']:.1%}). "
                        "FFT assumes equidistant sampling. Automatic interpolation onto uniform grid is enabled to preserve spectral fidelity."
                    )

                fc1, fc2, fc3, fc4 = st.columns(4)
                fft_window = fc1.selectbox("FFT window", ["Hann", "Hamming", "Blackman", "Bartlett", "None"], key="fft_win_sel")
                fft_detrend = fc2.toggle("Linear detrend", True, key="fft_detrend_tog")
                fft_plot_type = fc3.selectbox("Display spectrum", ["Power spectrum", "Amplitude spectrum"], key="fft_type_sel")
                fft_resample = fc4.toggle("Enforce uniform resampling", True, key="fft_resamp_tog")

                try:
                    fr = fft_analysis(
                        target["x"],
                        target["analysis_y"],
                        detrend=fft_detrend,
                        window=fft_window,
                        resample_if_nonuniform=fft_resample,
                    )

                    fk1, fk2, fk3, fk4 = st.columns(4)
                    fk1.metric("DC Component", f"{fr['dc_component']:.5g}")
                    fk2.metric("Dominant Frequency", f"{fr['dominant_frequency_per_nm']:.4g} cycles/nm")
                    fk3.metric("Dominant Spatial Period", f"{fr['dominant_period_nm']:.4g} nm")
                    fk4.metric("Nyquist Frequency", f"{fr['nyquist_frequency_per_nm']:.4g} cycles/nm")

                    y_fft = fr["power"] if fft_plot_type == "Power spectrum" else fr["amplitude"]
                    y_axis_fft_label = "Power |X(f)|²" if fft_plot_type == "Power spectrum" else "Amplitude |X(f)|"

                    ffig = go.Figure()
                    ffig.add_trace(
                        go.Scatter(
                            x=fr["frequency_per_nm"],
                            y=y_fft,
                            mode="lines",
                            name="FFT Spectrum",
                            line=dict(color="#2563EB", width=2),
                            hovertemplate="<b>f: %{x:.5f} cycles/nm</b><br>Period: %{customdata:.2f} nm<br>Signal: %{y:.5g}<extra></extra>",
                            customdata=fr["period_nm"],
                        )
                    )
                    ffig.update_layout(
                        template="plotly_white",
                        xaxis_title="Spatial frequency (cycles/nm)",
                        yaxis_title=y_axis_fft_label,
                        title=f"Fourier {fft_plot_type} — {target_name}",
                    )
                    st.plotly_chart(ffig, use_container_width=True)
                    st.caption("Note: Horizontal axis represents Fourier-conjugate spatial frequency across wavelength (cycles/nm), corresponding to periodic spectral modulation in nanometers.")

                    fft_df = pd.DataFrame({
                        "Frequency_cycles_per_nm": fr["frequency_per_nm"],
                        "Spatial_Period_nm": fr["period_nm"],
                        "Amplitude": fr["amplitude"],
                        "Power": fr["power"],
                    })
                    st.download_button(
                        label="📥 Download Fourier Spectrum Data (CSV)",
                        data=fft_df.to_csv(index=False).encode("utf-8-sig"),
                        file_name=f"{target_name}_fft_spectrum.csv",
                        mime="text/csv",
                    )
                except Exception as exc:
                    st.error(f"Fourier transform error: {exc}")

            # SUBTAB B: WAVELETS
            with subtab_wavelet:
                st.markdown("#### Discrete Wavelet Transform (DWT Denoising)")
                wc1, wc2, wc3, wc4 = st.columns(4)
                wavelet = wc1.selectbox("DWT Wavelet", ["db4", "db2", "sym4", "coif3", "bior2.2"], key="dwt_wav_sel")
                thresh_rule = wc2.selectbox("Threshold Rule", ["VisuShrink", "SURE", "Minimax"], key="dwt_rule_sel")
                thresh_scale = wc3.number_input("Threshold scale factor", 0.1, 5.0, 1.0, 0.1, key="dwt_scale_in")
                thresh_mode = wc4.selectbox("Threshold mode", ["soft", "hard"], key="dwt_mode_sel")

                dwt_res = wavelet_denoise_full(
                    target["analysis_y"],
                    wavelet=wavelet,
                    threshold_scale=float(thresh_scale),
                    threshold_rule=thresh_rule,
                    mode=thresh_mode,
                )

                wk1, wk2, wk3 = st.columns(3)
                wk1.metric("Noise SD Estimate σ", f"{dwt_res['sigma']:.5g}")
                wk2.metric("Applied Threshold λ", f"{dwt_res['threshold']:.5g}")
                wk3.metric("Decomposition Level", f"{dwt_res['level']}")

                wfig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, subplot_titles=["Reconstructed vs Original Spectrum", "Denoising Residuals (Original - Denoised)"])
                wfig.add_trace(go.Scatter(x=target["x"], y=target["analysis_y"], name="Original", line=dict(color="#94A3B8")), row=1, col=1)
                wfig.add_trace(go.Scatter(x=target["x"], y=dwt_res["denoised"], name="Denoised (DWT)", line=dict(color="#059669", width=2)), row=1, col=1)
                wfig.add_trace(go.Scatter(x=target["x"], y=dwt_res["residuals"], name="Residuals", line=dict(color="#EA580C", width=1.5)), row=2, col=1)
                wfig.update_layout(template="plotly_white", height=500)
                st.plotly_chart(wfig, use_container_width=True)

                dwt_df = pd.DataFrame({
                    "Wavelength_nm": target["x"],
                    "Original_Signal": target["analysis_y"],
                    "Denoised_Signal": dwt_res["denoised"],
                    "Residuals": dwt_res["residuals"],
                })
                st.download_button(
                    label="📥 Download DWT Denoised Spectrum (CSV)",
                    data=dwt_df.to_csv(index=False).encode("utf-8-sig"),
                    file_name=f"{target_name}_dwt_denoised.csv",
                    mime="text/csv",
                    key="download_dwt_denoised",
                )

                st.markdown("#### Continuous Wavelet Transform (CWT Scalogram)")
                cw1, cw2, cw3 = st.columns(3)
                cwave = cw1.selectbox("Mother wavelet", ["morl", "mexh", "gaus1", "gaus2"], key="cwt_wav_sel")
                smin = cw2.number_input("Min scale", 1, 128, 1, key="cwt_smin")
                smax = cw3.number_input("Max scale", 2, 256, 64, key="cwt_smax")

                cwt = cwt_analysis(target["x"], target["analysis_y"], wavelet=cwave, min_scale=int(smin), max_scale=int(smax))
                hfig = go.Figure(go.Heatmap(x=cwt["x_nm"], y=cwt["scales"], z=cwt["power"], colorscale="Viridis"))
                hfig.update_layout(template="plotly_white", xaxis_title="Wavelength (nm)", yaxis_title="Wavelet scale", title="CWT Power Scalogram")
                st.plotly_chart(hfig, use_container_width=True)

    # -------------------------------------------------------------------------
    # TAB 3: CALIBRATION & METHOD VALIDATION
    # -------------------------------------------------------------------------
    with tabs[3]:
        st.markdown("#### Beer–Lambert Calibration Curve")
        st.caption("Enter concentration and analytical response directly. No external spreadsheet is required.")
        cal = st.data_editor(
            pd.DataFrame({"Concentration": [0., 1., 2., 3., 4.], "Response": [np.nan] * 5}),
            num_rows="dynamic",
            use_container_width=True,
            key="calibration_table",
        )
        c1, c2, c3, c4 = st.columns(4)
        unit = c1.selectbox("Concentration unit", ["µg/mL", "mg/L", "mmol/L", "mol/L"])
        mw = c2.number_input("Molecular weight (g/mol)", min_value=0.0, value=0.0, step=0.001)
        path = c3.number_input("Path length (cm)", min_value=0.001, value=1.0, step=0.1)
        sigma_mode = c4.selectbox("σ for LOD/LOQ", ["Regression residual SD (Sy/x)", "Independent blank preparations", "Manual response SD"])
        sigma_manual = None
        if sigma_mode == "Manual response SD":
            sigma_manual = st.number_input("σ value", min_value=0.0, value=0.0, format="%.8g")
            if sigma_manual == 0:
                st.info("Enter a positive response SD and document how it was estimated.")
        elif sigma_mode == "Independent blank preparations":
            st.caption("Enter the measured responses of independently prepared blanks, using the same analytical procedure as the samples. Sample SD (n−1) is used.")
            blanks = st.data_editor(
                pd.DataFrame({"Blank response": [np.nan] * 10}),
                num_rows="dynamic", use_container_width=True, key="blank_responses_table",
            )
            blank_values = pd.to_numeric(blanks["Blank response"], errors="coerce").to_numpy(float)
            if np.isfinite(blank_values).sum() >= 3:
                try:
                    blank_stats = independent_blank_statistics(blank_values)
                    sigma_manual = float(blank_stats["sd"])
                    st.caption(f"Independent blanks: n={blank_stats['n']}; mean={blank_stats['mean']:.8g}; sample SD={sigma_manual:.8g}")
                except ValueError as exc:
                    st.error(str(exc))
        cx = pd.to_numeric(cal["Concentration"], errors="coerce").to_numpy(float)
        cy = pd.to_numeric(cal["Response"], errors="coerce").to_numpy(float)
        mask = np.isfinite(cx) & np.isfinite(cy)
        if np.count_nonzero(mask) >= 3 and (
            sigma_mode == "Regression residual SD (Sy/x)" or
            (sigma_manual is not None and sigma_manual > 0)
        ):
            try:
                cr = linear_calibration(cx[mask], cy[mask], sigma=sigma_manual, molecular_weight_g_mol=(mw or None), path_length_cm=path, concentration_unit=unit)
                km1, km2, km3, km4 = st.columns(4)
                km1.metric("Slope", f"{cr.slope:.8g}")
                km2.metric("Intercept", f"{cr.intercept:.8g}")
                km3.metric("R²", f"{cr.r2:.8f}")
                km4.metric("Sy/x", f"{cr.syx:.8g}")
                lm1, lm2, lm3 = st.columns(3)
                lm1.metric("LOD", f"{cr.lod:.8g} {unit}" if cr.lod is not None else "—")
                lm2.metric("LOQ", f"{cr.loq:.8g} {unit}" if cr.loq is not None else "—")
                lm3.metric("Molar absorptivity ε", f"{cr.epsilon_L_mol_cm:.8g} L·mol⁻¹·cm⁻¹" if cr.epsilon_L_mol_cm is not None else "MW/unit needed")
                cfig = go.Figure()
                cfig.add_trace(go.Scatter(x=cx[mask], y=cy[mask], mode="markers", name="Standards"))
                order = np.argsort(cx[mask])
                xx = cx[mask][order]
                cfig.add_trace(go.Scatter(x=xx, y=cr.intercept + cr.slope * xx, mode="lines", name="Linear fit"))
                cfig.update_layout(template="plotly_white", xaxis_title=f"Concentration ({unit})", yaxis_title="Response", title="Calibration curve")
                st.plotly_chart(cfig, use_container_width=True)
                st.dataframe(pd.DataFrame({"Concentration": cx[mask], "Observed": cy[mask], "Predicted": cr.predicted, "Residual": cr.residuals}), use_container_width=True, hide_index=True)
                with st.expander("Statistical diagnostics and inverse prediction"):
                    xcal, ycal = cx[mask], cy[mask]
                    lv = linearity_validation(xcal, ycal, sigma=sigma_manual)
                    st.write({
                        "Slope 95% CI": lv.slope_ci95,
                        "Intercept 95% CI": lv.intercept_ci95,
                        "Residual degrees of freedom": len(xcal) - 2,
                        "LOD/LOQ sigma source": sigma_mode,
                    })
                    rfig = go.Figure(go.Scatter(x=cr.predicted, y=cr.residuals, mode="markers", name="Residuals"))
                    rfig.add_hline(y=0, line_dash="dash")
                    rfig.update_layout(template="plotly_white", xaxis_title="Fitted response",
                                       yaxis_title="Observed − fitted", title="Calibration residuals")
                    st.plotly_chart(rfig, use_container_width=True)
                    if len(xcal) >= 4 and np.unique(xcal).size >= 3:
                        mandel = mandel_fitting_test(xcal, ycal)
                        st.write(f"Linear vs quadratic (Mandel): F={mandel['f']:.5g}, p={mandel['p_value']:.5g}. This tests curvature, not method suitability on its own.")
                    if np.unique(xcal).size >= 3 and len(xcal) > np.unique(xcal).size:
                        lof = lack_of_fit_test(xcal, ycal)
                        if lof["status"] == "ok":
                            st.write(f"Replicated-level lack of fit: F={lof['f']:.5g}, p={lof['p_value']:.5g}; pure-error df={lof['df_pure_error']}.")
                        else:
                            st.caption("Lack-of-fit is undefined because the replicate pure-error variance is zero.")
                    else:
                        st.caption("Lack-of-fit needs independently replicated responses at calibration levels.")
                    if len(xcal) >= 5:
                        try:
                            bp = breusch_pagan_calibration_test(xcal, ycal)
                            st.write(f"Breusch–Pagan variance diagnostic: p={bp['p_value']:.5g}. Weighting requires a defensible variance model.")
                        except ValueError as exc:
                            st.caption(str(exc))
                    u1, u2 = st.columns(2)
                    unknown_response = u1.number_input("Mean unknown response", value=0.0, format="%.8g", key="unknown_response_cal")
                    unknown_n = u2.number_input("Independent unknown readings", min_value=1, value=1, step=1, key="unknown_replicates_cal")
                    if st.button("Estimate unknown with approximate 95% CI", key="inverse_prediction_cal"):
                        prediction = inverse_prediction_interval(xcal, ycal, unknown_response,
                                                                  unknown_replicates=int(unknown_n))
                        st.write(f"Concentration: {prediction['concentration']:.8g} {unit}; approximate 95% CI: "
                                 f"[{prediction['lower']:.8g}, {prediction['upper']:.8g}] {unit}.")
                        if prediction["concentration"] < np.min(xcal) or prediction["concentration"] > np.max(xcal):
                            st.warning("This estimate extrapolates beyond the calibration range.")
            except Exception as exc:
                st.error(str(exc))
        else:
            st.info("Enter at least three complete calibration pairs and a positive σ estimate for the selected method.")

    # -------------------------------------------------------------------------
    # TAB 4: STOICHIOMETRY & MULTICOMPONENT
    # -------------------------------------------------------------------------
    with tabs[4]:
        jtab, mrtab = st.tabs(["Job method", "Mole-ratio method"])
        with jtab:
            jdf = st.data_editor(pd.DataFrame({"Mole fraction A": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9], "Response": [np.nan] * 9}), num_rows="dynamic", use_container_width=True, key="job_table")
            jx = pd.to_numeric(jdf.iloc[:, 0], errors="coerce").to_numpy(float)
            jy = pd.to_numeric(jdf.iloc[:, 1], errors="coerce").to_numpy(float)
            jm = np.isfinite(jx) & np.isfinite(jy)
            if np.count_nonzero(jm) >= 3:
                try:
                    jr = job_method(jx[jm], jy[jm])
                    st.metric("Estimated mole fraction at maximum", f"{jr['x_peak']:.5f}")
                    st.metric("Estimated A:B molar ratio", f"{jr['ratio_a_to_b']:.5g}:1")
                    jf = go.Figure(go.Scatter(x=jr["x"], y=jr["y"], mode="lines+markers"))
                    jf.update_layout(template="plotly_white", xaxis_title="Mole fraction A", yaxis_title="Response", title="Job plot")
                    st.plotly_chart(jf, use_container_width=True)
                except Exception as exc:
                    st.error(str(exc))
            else:
                st.info("Enter at least three complete Job-method points.")
        with mrtab:
            mrdf = st.data_editor(pd.DataFrame({"Reagent/analyte molar ratio": [0., 0.5, 1., 1.5, 2., 2.5, 3.], "Response": [np.nan] * 7}), num_rows="dynamic", use_container_width=True, key="mr_table")
            mx = pd.to_numeric(mrdf.iloc[:, 0], errors="coerce").to_numpy(float)
            my = pd.to_numeric(mrdf.iloc[:, 1], errors="coerce").to_numpy(float)
            mm = np.isfinite(mx) & np.isfinite(my)
            if np.count_nonzero(mm) >= 6:
                try:
                    mr = mole_ratio_method(mx[mm], my[mm])
                    st.metric("Segmented-regression breakpoint", f"{mr['breakpoint_ratio']:.6g}")
                    mf = go.Figure(go.Scatter(x=mr["x"], y=mr["y"], mode="markers", name="Data"))
                    x1 = np.linspace(np.min(mr["x"]), mr["breakpoint_ratio"], 100)
                    x2 = np.linspace(mr["breakpoint_ratio"], np.max(mr["x"]), 100)
                    mf.add_trace(go.Scatter(x=x1, y=mr["intercept1"] + mr["slope1"] * x1, mode="lines", name="Segment 1"))
                    mf.add_trace(go.Scatter(x=x2, y=mr["intercept2"] + mr["slope2"] * x2, mode="lines", name="Segment 2", line=dict(dash="dash")))
                    mf.update_layout(template="plotly_white", xaxis_title="Reagent/analyte molar ratio", yaxis_title="Response", title="Mole-ratio plot")
                    st.plotly_chart(mf, use_container_width=True)
                    st.write(f"Segment R²: {mr['r2_1']:.6f} and {mr['r2_2']:.6f}")
                except Exception as exc:
                    st.error(str(exc))
            else:
                st.info("Enter at least six complete mole-ratio points.")

    # -------------------------------------------------------------------------
    # TAB 5: STANDARD ADDITION
    # -------------------------------------------------------------------------
    with tabs[5]:
        sadf = st.data_editor(pd.DataFrame({"Added concentration": [0., 1., 2., 3., 4.], "Response": [np.nan] * 5}), num_rows="dynamic", use_container_width=True, key="sa_table")
        dilution = st.number_input("Overall dilution factor back to original sample", min_value=0.000001, value=1.0, step=0.1)
        sx = pd.to_numeric(sadf.iloc[:, 0], errors="coerce").to_numpy(float)
        sy = pd.to_numeric(sadf.iloc[:, 1], errors="coerce").to_numpy(float)
        sm = np.isfinite(sx) & np.isfinite(sy)
        if np.count_nonzero(sm) >= 3:
            try:
                sr = standard_addition(sx[sm], sy[sm], dilution_factor=dilution)
                s1, s2, s3, s4 = st.columns(4)
                s1.metric("Slope", f"{sr['slope']:.8g}")
                s2.metric("R²", f"{sr['r2']:.8f}")
                s3.metric("x-intercept", f"{sr['x_intercept']:.8g}")
                s4.metric("Original sample concentration", f"{sr['sample_concentration_original']:.8g}")
                sf = go.Figure()
                sf.add_trace(go.Scatter(x=sx[sm], y=sy[sm], mode="markers", name="Data"))
                xx = np.linspace(min(np.min(sx[sm]), sr["x_intercept"]), np.max(sx[sm]), 150)
                sf.add_trace(go.Scatter(x=xx, y=sr["intercept"] + sr["slope"] * xx, mode="lines", name="Fit"))
                sf.update_layout(template="plotly_white", xaxis_title="Added concentration", yaxis_title="Response", title="Standard-addition plot")
                st.plotly_chart(sf, use_container_width=True)
            except Exception as exc:
                st.error(str(exc))
        else:
            st.info("Enter at least three complete standard-addition points.")

    # -------------------------------------------------------------------------
    # TAB 6: CHEMOMETRICS SUITE
    # -------------------------------------------------------------------------
    with tabs[6]:
        render_chemometrics(processed)

    # -------------------------------------------------------------------------
    # TAB 7: DATA & METRICS
    # -------------------------------------------------------------------------
    with tabs[7]:
        if processed:
            if not metrics:
                metrics = [{"Curve": s["name"], **asdict(calculate_metrics(s["x"], s["analysis_y"]))}
                           for s in processed]
            full_auc_unit = auc_unit(derivative_order, _signal_base_unit(conversion, norm))
            full_auc_angstrom_unit = auc_unit_angstrom(derivative_order, _signal_base_unit(conversion, norm))
            md = pd.DataFrame(metrics).rename(columns={
                "lambda_max": "λmax (nm)",
                "y_max": "Signal at λmax",
                "lambda_min": "λmin (nm)",
                "y_min": "Signal at λmin",
                "area": f"Signed AUC full ({full_auc_unit})",
                "absolute_area": f"Absolute AUC full ({full_auc_unit})",
                "centroid": "Centroid (nm)",
                "fwhm": "FWHM (nm)",
                "peak_count": "Peaks",
            })
            md[f"Signed AUC ({full_auc_angstrom_unit})"] = md[f"Signed AUC full ({full_auc_unit})"] * 10.0
            md[f"Absolute AUC ({full_auc_angstrom_unit})"] = md[f"Absolute AUC full ({full_auc_unit})"] * 10.0
            st.markdown("#### Spectral metrics")
            st.dataframe(md, use_container_width=True, hide_index=True)
            st.markdown("#### Detected peaks")
            st.dataframe(pd.DataFrame(peak_rows), use_container_width=True, hide_index=True) if peak_rows else st.info("No peaks at current prominence threshold.")
            st.markdown("#### Signal at selected wavelengths")
            wtxt = st.text_input("Wavelengths (comma separated)", "270", key="extract_wavelengths")
            req = []
            for token in wtxt.replace(";", ",").split(","):
                try:
                    req.append(float(token.strip()))
                except Exception:
                    pass
            rows = [{"Curve": s["name"], "Wavelength (nm)": w, "Signal": signal_at_wavelength(s["x"], s["analysis_y"], w)} for s in processed for w in req]
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            st.markdown("#### S/N estimate")
            n1, n2 = st.columns(2)
            nmin = n1.number_input("Noise region from", value=max(xlo, xhi - (xhi - xlo) * .1), key="snr_min")
            nmax = n2.number_input("Noise region to", value=xhi, key="snr_max")
            sn = [{"Curve": s["name"], **estimate_snr(s["x"], s["analysis_y"], nmin, nmax)} for s in processed]
            st.dataframe(pd.DataFrame(sn), use_container_width=True, hide_index=True)
        else:
            st.info("Load spectra to view metrics and processed data.")

    # -------------------------------------------------------------------------
    # TAB 8: PROJECT & EXPORT
    # -------------------------------------------------------------------------
    with tabs[8]:
        st.markdown("### Reproducible Project Workspace")
        st.caption("Project files save raw spectra and processing/plot settings separately, so reopening recalculates the workspace without double-processing.")
        if spectra:
            settings = capture_settings(st.session_state)
            pbytes = project_bytes(spectra, settings=settings, notes=st.session_state.get("_project_notes", ""))
            pc1, pc2 = st.columns(2)
            project_name = pc1.text_input("Project file name", "UVVis_Project")
            pc2.download_button("Save complete project", pbytes, safe_filename(project_name) + ".uvvisproj", "application/zip", use_container_width=True)
        else:
            st.info("Load at least one spectrum before saving a project.")

    st.divider()
    st.caption(f"UV-Vis Spectrum Studio v{APP_VERSION} · Shimadzu LabSolutions-inspired analytical spectroscopy and chemometrics workspace")
