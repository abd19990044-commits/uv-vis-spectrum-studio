from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .validation import linearity_validation, precision_summary, recovery_summary, lack_of_fit_test
from .multicomponent import (
    simultaneous_equations,
    q_absorbance_ratio,
    dual_wavelength,
    ratio_spectrum,
    mean_center_ratio,
    derivative_ratio,
)
from .peakfit import fit_peaks
from .project import load_project


def render_advanced_suite(processed: list[dict]) -> None:
    st.markdown("### Advanced analytical suite")
    st.caption("Method validation, multicomponent spectrophotometry, peak deconvolution and reproducible project inspection.")
    vtab, mtab, ptab, projtab = st.tabs(["Method validation", "Multicomponent UV-Vis", "Peak deconvolution", "Project / session"])

    with vtab:
        st.markdown("#### Linearity, LOD/LOQ and regression diagnostics")
        df = st.data_editor(
            pd.DataFrame({"Concentration": [0., 1., 2., 3., 4.], "Response": [np.nan] * 5}),
            num_rows="dynamic",
            use_container_width=True,
            key="adv_val_lin",
        )
        sigma_mode = st.selectbox("σ source", ["Regression residual SD (Sy/x)", "Manual σ"], key="adv_sigma_mode")
        sigma = None
        if sigma_mode == "Manual σ":
            sigma = st.number_input("Manual σ", min_value=0.0, value=0.0, format="%.8g", key="adv_sigma")
        x = pd.to_numeric(df.iloc[:, 0], errors="coerce").to_numpy(float)
        y = pd.to_numeric(df.iloc[:, 1], errors="coerce").to_numpy(float)
        mask = np.isfinite(x) & np.isfinite(y)
        if np.count_nonzero(mask) >= 3:
            try:
                result = linearity_validation(x[mask], y[mask], sigma=sigma)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Slope", f"{result.slope:.8g}")
                c2.metric("Intercept", f"{result.intercept:.8g}")
                c3.metric("R²", f"{result.r2:.8f}")
                c4.metric("Sy/x", f"{result.syx:.8g}")
                d1, d2, d3, d4 = st.columns(4)
                d1.metric("LOD (3.3σ/S)", f"{result.lod_33:.8g}" if result.lod_33 is not None else "—")
                d2.metric("LOQ (10σ/S)", f"{result.loq_10:.8g}" if result.loq_10 is not None else "—")
                d3.metric("Slope 95% CI", f"{result.slope_ci95[0]:.5g} … {result.slope_ci95[1]:.5g}")
                d4.metric("Intercept 95% CI", f"{result.intercept_ci95[0]:.5g} … {result.intercept_ci95[1]:.5g}")
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=x[mask], y=y[mask], mode="markers", name="Observed"))
                xx = np.linspace(np.min(x[mask]), np.max(x[mask]), 200)
                fig.add_trace(go.Scatter(x=xx, y=result.intercept + result.slope * xx, mode="lines", name="Fit"))
                fig.update_layout(template="plotly_white", xaxis_title="Concentration", yaxis_title="Response", title="Validation calibration")
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(pd.DataFrame({"Concentration": x[mask], "Observed": y[mask], "Predicted": result.predicted, "Residual": result.residuals}), use_container_width=True, hide_index=True)
                try:
                    lof = lack_of_fit_test(x[mask], y[mask])
                    st.write(f"Lack-of-fit: F = {lof['f']:.5g}, p = {lof['p_value']:.5g}")
                except Exception:
                    st.caption("Lack-of-fit becomes available when replicated responses are entered at calibration levels.")
            except Exception as exc:
                st.error(str(exc))

        st.markdown("#### Precision / recovery")
        precision_tab, recovery_tab = st.tabs(["Precision", "Recovery"])
        with precision_tab:
            vals = st.data_editor(pd.DataFrame({"Replicate result": [np.nan] * 6}), num_rows="dynamic", use_container_width=True, key="adv_precision")
            arr = pd.to_numeric(vals.iloc[:, 0], errors="coerce").dropna().to_numpy(float)
            if len(arr) >= 2:
                st.dataframe(pd.DataFrame([precision_summary(arr)]), use_container_width=True, hide_index=True)
        with recovery_tab:
            rec = st.data_editor(pd.DataFrame({"Nominal": [np.nan] * 6, "Found": [np.nan] * 6}), num_rows="dynamic", use_container_width=True, key="adv_recovery")
            nominal = pd.to_numeric(rec.iloc[:, 0], errors="coerce").to_numpy(float)
            found = pd.to_numeric(rec.iloc[:, 1], errors="coerce").to_numpy(float)
            good = np.isfinite(nominal) & np.isfinite(found) & (nominal != 0)
            if np.count_nonzero(good) >= 2:
                summary = recovery_summary(found[good], nominal[good])
                m1, m2 = st.columns(2)
                m1.metric("Mean recovery", f"{summary['mean_recovery_percent']:.4f}%")
                m2.metric("Recovery RSD", f"{summary['rsd_percent']:.4f}%")
                st.dataframe(pd.DataFrame({"Nominal": nominal[good], "Found": found[good], "Recovery %": summary["recovery_percent"]}), use_container_width=True, hide_index=True)

    with mtab:
        method = st.selectbox(
            "Method",
            ["Simultaneous equations (2×2)", "Absorbance-ratio / Q-analysis", "Dual-wavelength", "Ratio spectrum from loaded curves"],
            key="adv_multi_method",
        )
        if method == "Simultaneous equations (2×2)":
            a, b = st.columns(2)
            A1 = a.number_input("Mixture A(λ1)", value=0.0)
            A2 = b.number_input("Mixture A(λ2)", value=0.0)
            c1, c2, c3, c4 = st.columns(4)
            ea1 = c1.number_input("εA, λ1", value=1.0)
            ea2 = c2.number_input("εA, λ2", value=1.0)
            eb1 = c3.number_input("εB, λ1", value=1.0)
            eb2 = c4.number_input("εB, λ2", value=1.0)
            path = st.number_input("Path length (cm)", value=1.0, min_value=0.001)
            if st.button("Solve concentrations", key="adv_sim_eq"):
                try:
                    result = simultaneous_equations(A1, A2, ea1, ea2, eb1, eb2, path)
                    st.success(f"Component A = {result['concentration_A']:.8g}; Component B = {result['concentration_B']:.8g}")
                    st.write(f"Matrix condition number: {result['condition_number']:.5g}")
                except Exception as exc:
                    st.error(str(exc))
        elif method == "Absorbance-ratio / Q-analysis":
            vals = st.columns(6)
            ai = vals[0].number_input("Aiso", value=0.0)
            al = vals[1].number_input("Aλ", value=0.0)
            eai = vals[2].number_input("εA iso", value=1.0)
            eal = vals[3].number_input("εA λ", value=1.0)
            ebi = vals[4].number_input("εB iso", value=1.0)
            ebl = vals[5].number_input("εB λ", value=1.0)
            path = st.number_input("Path length", value=1.0, min_value=0.001, key="adv_q_path")
            if st.button("Calculate Q-analysis", key="adv_q_btn"):
                try:
                    st.json(q_absorbance_ratio(ai, al, eai, eal, ebi, ebl, path))
                except Exception as exc:
                    st.error(str(exc))
        elif method == "Dual-wavelength":
            cols = st.columns(5)
            s1 = cols[0].number_input("Sample λ1", value=0.0)
            s2 = cols[1].number_input("Sample λ2", value=0.0)
            r1 = cols[2].number_input("Standard λ1", value=0.0)
            r2 = cols[3].number_input("Standard λ2", value=0.0)
            cs = cols[4].number_input("Standard concentration", value=1.0)
            if st.button("Calculate concentration", key="adv_dual"):
                try:
                    st.json(dual_wavelength(s1, s2, r1, r2, cs))
                except Exception as exc:
                    st.error(str(exc))
        else:
            if len(processed) < 2:
                st.info("Load at least two curves.")
            else:
                names = [s["name"] for s in processed]
                c1, c2 = st.columns(2)
                n1 = c1.selectbox("Numerator", names, key="adv_ratio_num")
                n2 = c2.selectbox("Divisor", names, index=1, key="adv_ratio_den")
                sp1 = next(s for s in processed if s["name"] == n1)
                sp2 = next(s for s in processed if s["name"] == n2)
                lo = max(sp1["x"].min(), sp2["x"].min())
                hi = min(sp1["x"].max(), sp2["x"].max())
                xx = np.linspace(lo, hi, min(len(sp1["x"]), len(sp2["x"])))
                y1 = np.interp(xx, sp1["x"], sp1["analysis_y"])
                y2 = np.interp(xx, sp2["x"], sp2["analysis_y"])
                _, ratio = ratio_spectrum(xx, y1, y2)
                operation = st.selectbox("Ratio processing", ["Raw ratio", "Mean-centered ratio", "1st derivative ratio", "2nd derivative ratio"])
                yy = ratio if operation == "Raw ratio" else mean_center_ratio(ratio) if operation == "Mean-centered ratio" else derivative_ratio(xx, ratio, 1 if operation.startswith("1st") else 2)
                fig = go.Figure(go.Scatter(x=xx, y=yy, mode="lines"))
                fig.update_layout(template="plotly_white", xaxis_title="Wavelength (nm)", yaxis_title=operation, title=f"{n1} / {n2}")
                st.plotly_chart(fig, use_container_width=True)

    with ptab:
        if not processed:
            st.info("Load at least one spectrum for peak fitting.")
        else:
            names = [s["name"] for s in processed]
            name = st.selectbox("Spectrum", names, key="adv_peak_curve")
            spectrum = next(v for v in processed if v["name"] == name)
            c1, c2, c3 = st.columns(3)
            shape = c1.selectbox("Peak shape", ["Gaussian", "Lorentzian", "Voigt", "Pseudo-Voigt"])
            centers_text = c2.text_input("Initial centers (nm, comma separated)", "270, 330")
            baseline = c3.selectbox("Baseline polynomial order", [0, 1, 2, 3], index=1)
            try:
                centers = [float(v.strip()) for v in centers_text.replace(";", ",").split(",") if v.strip()]
            except Exception:
                centers = []
            if st.button("Fit / deconvolute peaks", type="primary", key="adv_peak_fit"):
                try:
                    result = fit_peaks(spectrum["x"], spectrum["analysis_y"], centers, shape, int(baseline))
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=result["x"], y=result["y"], mode="lines", name="Observed"))
                    fig.add_trace(go.Scatter(x=result["x"], y=result["fit"], mode="lines", name="Total fit", line=dict(dash="dash")))
                    fig.add_trace(go.Scatter(x=result["x"], y=result["baseline"], mode="lines", name="Baseline", line=dict(dash="dot")))
                    rows = []
                    for comp in result["components"]:
                        fig.add_trace(go.Scatter(x=result["x"], y=comp["curve"] + result["baseline"], mode="lines", name=f"Peak {comp['peak']}"))
                        rows.append({k: v for k, v in comp.items() if k not in {"curve", "parameters"}})
                    fig.update_layout(template="plotly_white", xaxis_title="Wavelength (nm)", yaxis_title="Signal", title=f"{shape} deconvolution · R²={result['r2']:.6f}")
                    st.plotly_chart(fig, use_container_width=True)
                    st.metric("RMSE", f"{result['rmse']:.6g}")
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                except Exception as exc:
                    st.error(str(exc))

    with projtab:
        st.markdown("#### Unified v3 project workflow")
        st.info("Open a project from the **Project** panel at the top of the left sidebar. Save the complete reproducible project from **Publication & Project**. This keeps one authoritative restore path for raw spectra, processing settings and figure appearance.")
        upload = st.file_uploader("Inspect a project without replacing the current workspace", type=["uvvisproj", "zip"], key="adv_project_inspect")
        if upload is not None:
            try:
                project = load_project(upload.getvalue())
                st.success(f"Project format v{project['metadata'].get('version', 1)} · {len(project['spectra'])} spectra")
                st.write(project["notes"] or "No project notes.")
                st.dataframe(pd.DataFrame([{"Name": s["name"], "Points": len(s["x"]), "Source": s["source"]} for s in project["spectra"]]), use_container_width=True, hide_index=True)
            except Exception as exc:
                st.error(str(exc))
