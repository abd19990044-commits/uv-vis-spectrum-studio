from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .multicomponent import (
    derivative_ratio,
    dual_wavelength,
    mean_center_ratio,
    q_absorbance_ratio,
    ratio_spectrum,
    simultaneous_equations,
)
from .peakfit import fit_peaks
from .project import load_project
from .quality import absorbance_quality, derivative_quality
from .validation import (
    inverse_prediction_interval,
    lack_of_fit_test,
    linearity_validation,
    mandel_fitting_test,
    precision_summary,
    recovery_summary,
)


def _stretch_dataframe(data, **kwargs):
    st.dataframe(data, width="stretch", **kwargs)


def render_advanced_suite(processed: list[dict]) -> None:
    st.markdown("### Advanced analytical suite")
    st.caption(
        "Method validation, spectroscopy quality diagnostics, multicomponent spectrophotometry, "
        "peak deconvolution and reproducible project inspection."
    )
    vtab, qtab, mtab, ptab, projtab = st.tabs(
        ["Method validation", "Spectroscopy QC", "Multicomponent UV-Vis", "Peak deconvolution", "Project / session"]
    )

    with vtab:
        st.markdown("#### Linearity, LOD/LOQ and regression diagnostics")
        df = st.data_editor(
            pd.DataFrame({"Concentration": [0.0, 1.0, 2.0, 3.0, 4.0], "Response": [np.nan] * 5}),
            num_rows="dynamic",
            width="stretch",
            key="adv_val_lin",
        )
        sigma_mode = st.selectbox(
            "σ source",
            ["Regression residual SD (Sy/x)", "Manual σ"],
            key="adv_sigma_mode",
        )
        sigma = None
        if sigma_mode == "Manual σ":
            sigma = st.number_input("Manual σ", min_value=0.0, value=0.0, format="%.8g", key="adv_sigma")

        x = pd.to_numeric(df.iloc[:, 0], errors="coerce").to_numpy(float)
        y = pd.to_numeric(df.iloc[:, 1], errors="coerce").to_numpy(float)
        mask = np.isfinite(x) & np.isfinite(y)
        if np.count_nonzero(mask) >= 3:
            try:
                xv, yv = x[mask], y[mask]
                result = linearity_validation(xv, yv, sigma=sigma)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Slope", f"{result.slope:.8g}")
                c2.metric("Intercept", f"{result.intercept:.8g}")
                c3.metric("R²", f"{result.r2:.8f}")
                c4.metric("Sy/x", f"{result.syx:.8g}")
                d1, d2, d3, d4 = st.columns(4)
                d1.metric("LOD (3.3σ/|S|)", f"{result.lod_33:.8g}" if result.lod_33 is not None else "—")
                d2.metric("LOQ (10σ/|S|)", f"{result.loq_10:.8g}" if result.loq_10 is not None else "—")
                d3.metric("Slope 95% CI", f"{result.slope_ci95[0]:.5g} … {result.slope_ci95[1]:.5g}")
                d4.metric("Intercept 95% CI", f"{result.intercept_ci95[0]:.5g} … {result.intercept_ci95[1]:.5g}")

                fig = go.Figure()
                fig.add_trace(go.Scatter(x=xv, y=yv, mode="markers", name="Observed"))
                xx = np.linspace(np.min(xv), np.max(xv), 200)
                fig.add_trace(
                    go.Scatter(x=xx, y=result.intercept + result.slope * xx, mode="lines", name="Linear fit")
                )
                fig.update_layout(
                    template="plotly_white",
                    xaxis_title="Concentration",
                    yaxis_title="Response",
                    title="Validation calibration",
                )
                st.plotly_chart(fig, width="stretch")

                residual_fig = go.Figure()
                residual_fig.add_trace(
                    go.Scatter(x=result.predicted, y=result.residuals, mode="markers", name="Residuals")
                )
                residual_fig.add_hline(y=0.0, line_dash="dash")
                residual_fig.update_layout(
                    template="plotly_white",
                    xaxis_title="Predicted response",
                    yaxis_title="Residual",
                    title="Residual diagnostic",
                )
                st.plotly_chart(residual_fig, width="stretch")
                _stretch_dataframe(
                    pd.DataFrame(
                        {
                            "Concentration": xv,
                            "Observed": yv,
                            "Predicted": result.predicted,
                            "Residual": result.residuals,
                        }
                    ),
                    hide_index=True,
                )

                try:
                    mandel = mandel_fitting_test(xv, yv)
                    if mandel["quadratic_improvement_significant"]:
                        st.warning(
                            f"Mandel fitting test: quadratic curvature is statistically significant "
                            f"(F={mandel['f']:.5g}, p={mandel['p_value']:.5g}). "
                            "Do not rely on R² alone; inspect chemistry, range and residual structure before choosing a model."
                        )
                    else:
                        st.success(
                            f"Mandel fitting test: no significant quadratic improvement at α={mandel['alpha']:.2g} "
                            f"(F={mandel['f']:.5g}, p={mandel['p_value']:.5g})."
                        )
                except Exception as exc:
                    st.caption(f"Mandel test unavailable: {exc}")

                try:
                    lof = lack_of_fit_test(xv, yv)
                    text = f"Lack-of-fit: F = {lof['f']:.5g}, p = {lof['p_value']:.5g}"
                    if lof["p_value"] < 0.05:
                        st.warning(text + " · significant lack-of-fit at α=0.05.")
                    else:
                        st.write(text)
                except Exception:
                    st.caption("Lack-of-fit becomes available when replicated responses are entered at calibration levels.")

                st.markdown("##### Unknown concentration by inverse prediction")
                uc1, uc2, uc3 = st.columns(3)
                unknown_response = uc1.number_input("Unknown mean response", value=float(np.mean(yv)), key="adv_unknown_y")
                unknown_reps = uc2.number_input("Unknown replicates", 1, 100, 1, key="adv_unknown_reps")
                confidence = uc3.selectbox("Confidence", [0.90, 0.95, 0.99], index=1, key="adv_unknown_conf")
                try:
                    inv = inverse_prediction_interval(
                        xv,
                        yv,
                        unknown_response,
                        unknown_replicates=int(unknown_reps),
                        confidence=float(confidence),
                    )
                    st.write(
                        f"Estimated concentration = **{inv['concentration']:.8g}**; "
                        f"{100*inv['confidence']:.0f}% CI = **[{inv['lower']:.8g}, {inv['upper']:.8g}]**"
                    )
                except Exception as exc:
                    st.caption(f"Inverse prediction unavailable: {exc}")
            except Exception as exc:
                st.error(str(exc))

        st.markdown("#### Precision / recovery")
        precision_tab, recovery_tab = st.tabs(["Precision", "Recovery"])
        with precision_tab:
            vals = st.data_editor(
                pd.DataFrame({"Replicate result": [np.nan] * 6}),
                num_rows="dynamic",
                width="stretch",
                key="adv_precision",
            )
            arr = pd.to_numeric(vals.iloc[:, 0], errors="coerce").dropna().to_numpy(float)
            if len(arr) >= 2:
                _stretch_dataframe(pd.DataFrame([precision_summary(arr)]), hide_index=True)
        with recovery_tab:
            rec = st.data_editor(
                pd.DataFrame({"Nominal": [np.nan] * 6, "Found": [np.nan] * 6}),
                num_rows="dynamic",
                width="stretch",
                key="adv_recovery",
            )
            nominal = pd.to_numeric(rec.iloc[:, 0], errors="coerce").to_numpy(float)
            found = pd.to_numeric(rec.iloc[:, 1], errors="coerce").to_numpy(float)
            good = np.isfinite(nominal) & np.isfinite(found) & (nominal != 0)
            if np.count_nonzero(good) >= 2:
                summary = recovery_summary(found[good], nominal[good])
                m1, m2 = st.columns(2)
                m1.metric("Mean recovery", f"{summary['mean_recovery_percent']:.4f}%")
                m2.metric("Recovery RSD", f"{summary['rsd_percent']:.4f}%")
                _stretch_dataframe(
                    pd.DataFrame(
                        {
                            "Nominal": nominal[good],
                            "Found": found[good],
                            "Recovery %": summary["recovery_percent"],
                        }
                    ),
                    hide_index=True,
                )

    with qtab:
        st.markdown("#### Spectroscopy quality diagnostics")
        st.caption(
            "These are diagnostic safeguards, not universal rejection rules. Instrument performance, bandwidth, "
            "sample chemistry and method validation remain authoritative."
        )
        if not processed:
            st.info("Load at least one spectrum to run spectroscopy QC.")
        else:
            names = [s["name"] for s in processed]
            selected = st.selectbox("Spectrum", names, key="qc_spectrum")
            spectrum = next(s for s in processed if s["name"] == selected)
            raw_y = np.asarray(spectrum.get("raw_y", spectrum.get("y", spectrum["analysis_y"])), dtype=float)
            aq = absorbance_quality(raw_y)
            q1, q2, q3 = st.columns(3)
            q1.metric("Maximum raw signal", f"{aq['max_absorbance']:.6g}")
            q2.metric("Minimum raw signal", f"{aq.get('min_absorbance', np.nan):.6g}")
            q3.metric("Absorbance QC", aq["status"])
            for warning in aq["warnings"]:
                st.warning(warning)

            d1, d2, d3 = st.columns(3)
            derivative_order = d1.selectbox("Derivative order to assess", [0, 1, 2, 3, 4], index=4, key="qc_deriv_order")
            sg_window = d2.number_input("SG window (points)", 3, 501, 11, 2, key="qc_sg_window")
            sg_poly = d3.number_input("Requested polynomial order", 1, 12, 3, 1, key="qc_sg_poly")
            fwhm_text = st.text_input(
                "Representative FWHM (nm, optional)",
                "",
                key="qc_fwhm",
                help="Use a representative experimentally resolved band if available. Leave blank if unknown.",
            )
            try:
                fwhm = float(fwhm_text) if fwhm_text.strip() else None
                dq = derivative_quality(
                    spectrum["x"],
                    order=int(derivative_order),
                    smoothing_window_points=int(sg_window),
                    requested_polyorder=int(sg_poly),
                    fwhm_nm=fwhm,
                )
                rows = {
                    "Median Δλ (nm)": dq.median_step_nm,
                    "Max grid deviation (%)": dq.max_step_deviation_percent,
                    "Effective polyorder": dq.effective_polyorder,
                    "Effective SG window (points)": dq.smoothing_window_points,
                    "SG span (nm)": dq.smoothing_window_nm,
                    "Points/FWHM": dq.points_per_fwhm,
                    "Window/FWHM": dq.window_to_fwhm_ratio,
                    "Status": dq.status,
                }
                _stretch_dataframe(pd.DataFrame([rows]), hide_index=True)
                for warning in dq.warnings:
                    st.warning(warning)
            except Exception as exc:
                st.error(f"Derivative QC could not be calculated: {exc}")

    with mtab:
        method = st.selectbox(
            "Method",
            [
                "Simultaneous equations (2×2)",
                "Absorbance-ratio / Q-analysis",
                "Dual-wavelength",
                "Ratio spectrum from loaded curves",
            ],
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
                    st.success(
                        f"Component A = {result['concentration_A']:.8g}; "
                        f"Component B = {result['concentration_B']:.8g}"
                    )
                    st.write(
                        f"Matrix condition number: **{result['condition_number']:.5g}** "
                        f"· status: **{result['conditioning_status']}**"
                    )
                    if result.get("conditioning_warning"):
                        st.warning(result["conditioning_warning"])
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
                    result = q_absorbance_ratio(ai, al, eai, eal, ebi, ebl, path)
                    if result.get("warning"):
                        st.warning(result["warning"])
                    st.json(result)
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
                operation = st.selectbox(
                    "Ratio processing",
                    ["Raw ratio", "Mean-centered ratio", "1st derivative ratio", "2nd derivative ratio"],
                )
                if operation == "Raw ratio":
                    yy = ratio
                elif operation == "Mean-centered ratio":
                    yy = mean_center_ratio(ratio)
                else:
                    yy = derivative_ratio(xx, ratio, 1 if operation.startswith("1st") else 2)
                fig = go.Figure(go.Scatter(x=xx, y=yy, mode="lines"))
                fig.update_layout(
                    template="plotly_white",
                    xaxis_title="Wavelength (nm)",
                    yaxis_title=operation,
                    title=f"{n1} / {n2}",
                )
                st.plotly_chart(fig, width="stretch")

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
                    fig.add_trace(
                        go.Scatter(
                            x=result["x"],
                            y=result["fit"],
                            mode="lines",
                            name="Total fit",
                            line=dict(dash="dash"),
                        )
                    )
                    fig.add_trace(
                        go.Scatter(
                            x=result["x"],
                            y=result["baseline"],
                            mode="lines",
                            name="Baseline",
                            line=dict(dash="dot"),
                        )
                    )
                    rows = []
                    for comp in result["components"]:
                        fig.add_trace(
                            go.Scatter(
                                x=result["x"],
                                y=comp["curve"] + result["baseline"],
                                mode="lines",
                                name=f"Peak {comp['peak']}",
                            )
                        )
                        rows.append({k: v for k, v in comp.items() if k not in {"curve", "parameters"}})
                    fig.update_layout(
                        template="plotly_white",
                        xaxis_title="Wavelength (nm)",
                        yaxis_title="Signal",
                        title=f"{shape} deconvolution · R²={result['r2']:.6f}",
                    )
                    st.plotly_chart(fig, width="stretch")
                    st.metric("RMSE", f"{result['rmse']:.6g}")
                    _stretch_dataframe(pd.DataFrame(rows), hide_index=True)
                except Exception as exc:
                    st.error(str(exc))

    with projtab:
        st.markdown("#### Unified project workflow")
        st.info(
            "Open a project from the Project panel at the top of the left sidebar. Save the complete reproducible "
            "project from Project & export. Project format v3 stores reproducibility metadata and can store audit-trail metadata."
        )
        upload = st.file_uploader(
            "Inspect a project without replacing the current workspace",
            type=["uvvisproj", "zip"],
            key="adv_project_inspect",
        )
        if upload is not None:
            try:
                project = load_project(upload.getvalue())
                st.success(
                    f"Project format v{project['metadata'].get('version', 1)} · {len(project['spectra'])} spectra"
                )
                st.write(project["notes"] or "No project notes.")
                if project.get("reproducibility"):
                    st.markdown("##### Reproducibility metadata")
                    st.json(project["reproducibility"])
                if project.get("audit_trail"):
                    st.markdown("##### Audit trail")
                    _stretch_dataframe(pd.DataFrame(project["audit_trail"]), hide_index=True)
                _stretch_dataframe(
                    pd.DataFrame(
                        [
                            {"Name": s["name"], "Points": len(s["x"]), "Source": s["source"]}
                            for s in project["spectra"]
                        ]
                    ),
                    hide_index=True,
                )
            except Exception as exc:
                st.error(str(exc))
