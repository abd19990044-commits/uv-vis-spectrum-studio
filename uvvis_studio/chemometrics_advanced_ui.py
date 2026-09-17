from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .chemometrics import pls_with_vip
from .chemometrics_advanced import (
    interval_pls,
    kennard_stone,
    nested_pls_evaluation,
    optimize_pls_components,
    spxy,
    vip_threshold_select,
    y_randomization_test,
)
from .chemometrics_basic_ui import _align_spectra


def render_advanced_chemometrics(processed: list[dict]) -> None:
    st.markdown("### Advanced chemometric validation")
    st.caption(
        "Dataset splitting, component optimization, nested validation, Y-randomization and wavelength/interval screening. "
        "Confirmatory claims should use nested validation or a genuinely independent locked test set."
    )
    if len(processed) < 5:
        st.info("Load at least five spectra to use advanced chemometric validation.")
        return
    try:
        wl, X, names = _align_spectra(processed)
    except Exception as exc:
        st.error(str(exc))
        return

    targets = st.data_editor(
        pd.DataFrame({"Sample": names, "Y": [np.nan] * len(names)}),
        width="stretch",
        hide_index=True,
        key="chem_adv_targets",
        disabled=["Sample"],
    )
    y = pd.to_numeric(targets["Y"], errors="coerce").to_numpy(float)
    good = np.isfinite(y)
    if np.count_nonzero(good) < 5:
        st.info("Enter at least five numerical Y values to activate the advanced tools.")
        return

    Xg = X[good]
    yg = y[good]
    ng = np.asarray(names)[good]
    spl, optt, nestedt, randt, vart = st.tabs(
        [
            "Train/test splitting",
            "PLS optimization",
            "Nested PLS",
            "Y-randomization",
            "Variable selection",
        ]
    )

    with spl:
        c1, c2, c3 = st.columns(3)
        method = c1.selectbox("Split method", ["Kennard-Stone", "SPXY"])
        frac = c2.slider("Training fraction", 0.5, 0.9, 0.7, 0.05)
        alpha = c3.slider("SPXY Y-weight", 0.0, 1.0, 0.5, 0.05, disabled=method != "SPXY")
        ntrain = max(2, min(len(Xg) - 1, int(round(len(Xg) * frac))))
        try:
            tr, te = (
                kennard_stone(Xg, ntrain)
                if method == "Kennard-Stone"
                else spxy(Xg, yg, ntrain, alpha)
            )
            st.write(f"Training samples: **{len(tr)}** · Test samples: **{len(te)}**")
            train_set = set(tr.tolist())
            st.dataframe(
                pd.DataFrame(
                    {
                        "Sample": ng,
                        "Set": ["Train" if i in train_set else "Test" for i in range(len(ng))],
                    }
                ),
                width="stretch",
                hide_index=True,
            )
            st.caption(
                "Kennard-Stone/SPXY are deterministic design-space splitters. Preserve the test set untouched after "
                "model/preprocessing/variable-selection decisions are made on the training data."
            )
        except Exception as exc:
            st.error(str(exc))

    with optt:
        c1, c2 = st.columns(2)
        maxc = c1.number_input(
            "Maximum PLS components",
            1,
            max(1, min(20, len(Xg) - 1, Xg.shape[1])),
            min(10, max(1, min(20, len(Xg) - 1, Xg.shape[1]))),
        )
        cv = c2.number_input("CV folds", 2, len(Xg), min(5, len(Xg)))
        try:
            result = optimize_pls_components(Xg, yg, int(maxc), int(cv))
            st.metric("CV-selected components", result["best_components"])
            st.metric("Minimum screening RMSECV", f"{result['best_rmsecv']:.6g}")
            st.metric("Q² at selected component count", f"{result['best_r2_cv']:.5f}")
            st.warning(result["selection_warning"])
            table = pd.DataFrame(result["results"])
            figure = go.Figure()
            figure.add_trace(
                go.Scatter(
                    x=table["components"],
                    y=table["rmsecv"],
                    mode="lines+markers",
                    name="RMSECV",
                )
            )
            figure.update_layout(
                template="plotly_white",
                xaxis_title="PLS components",
                yaxis_title="RMSECV",
                title="PLS component optimization",
            )
            st.plotly_chart(figure, width="stretch")
        except Exception as exc:
            st.error(str(exc))

    with nestedt:
        st.markdown("#### Nested cross-validation")
        st.caption(
            "The inner loop selects the number of latent variables using only outer-training samples; "
            "the held-out outer fold estimates predictive performance. This avoids reporting the same CV minimum used for tuning."
        )
        c1, c2, c3 = st.columns(3)
        maxc_nested = c1.number_input(
            "Maximum components",
            1,
            max(1, min(20, len(Xg) - 1, Xg.shape[1])),
            min(8, max(1, min(20, len(Xg) - 1, Xg.shape[1]))),
            key="chem_nested_maxc",
        )
        outer = c2.number_input(
            "Outer folds",
            2,
            max(2, len(Xg) - 1),
            min(5, max(2, len(Xg) - 1)),
            key="chem_nested_outer",
        )
        inner = c3.number_input(
            "Inner folds",
            2,
            max(2, len(Xg) - 1),
            min(5, max(2, len(Xg) - 1)),
            key="chem_nested_inner",
        )
        if st.button("Run nested PLS validation", type="primary", key="chem_nested_run"):
            try:
                result = nested_pls_evaluation(
                    Xg,
                    yg,
                    max_components=int(maxc_nested),
                    outer_folds=int(outer),
                    inner_folds=int(inner),
                )
                a, b, c, d = st.columns(4)
                a.metric("Nested Q²", f"{result['q2_nested']:.5f}")
                b.metric("Nested RMSEP", f"{result['rmsep_nested']:.6g}")
                c.metric("Nested MAE", f"{result['maep_nested']:.6g}")
                d.metric("Median LV", result["median_selected_components"])

                parity = go.Figure()
                parity.add_trace(
                    go.Scatter(x=yg, y=result["predicted"], mode="markers", name="Outer-fold predictions")
                )
                low = float(min(np.min(yg), np.min(result["predicted"])))
                high = float(max(np.max(yg), np.max(result["predicted"])))
                parity.add_trace(
                    go.Scatter(x=[low, high], y=[low, high], mode="lines", name="Identity", line=dict(dash="dash"))
                )
                parity.update_layout(
                    template="plotly_white",
                    xaxis_title="Reference Y",
                    yaxis_title="Nested-CV predicted Y",
                    title="Nested PLS prediction",
                )
                st.plotly_chart(parity, width="stretch")
                st.dataframe(pd.DataFrame(result["folds"]), width="stretch", hide_index=True)
                st.caption(
                    "Nested CV reduces tuning bias but does not replace external validation when an independent validation set is available."
                )
            except Exception as exc:
                st.error(str(exc))

    with randt:
        c1, c2, c3 = st.columns(3)
        nc = c1.number_input(
            "PLS components",
            1,
            max(1, min(15, len(Xg) - 1, Xg.shape[1])),
            min(3, max(1, min(15, len(Xg) - 1, Xg.shape[1]))),
            key="chem_rand_nc",
        )
        perms = c2.number_input("Permutations", 10, 1000, 100, 10)
        cv = c3.number_input("CV folds", 2, len(Xg), min(5, len(Xg)), key="chem_rand_cv")
        if st.button("Run Y-randomization", key="chem_rand_run"):
            try:
                result = y_randomization_test(Xg, yg, int(nc), int(perms), int(cv))
                a, b, c = st.columns(3)
                a.metric("Observed Q²", f"{result['observed_q2']:.5f}")
                b.metric("Permutation p", f"{result['p_value']:.5f}")
                c.metric("Null mean Q²", f"{result['null_mean']:.5f}")
                hist = go.Figure(go.Histogram(x=result["permuted_q2"], nbinsx=30))
                hist.add_vline(x=result["observed_q2"], line_dash="dash", annotation_text="Observed Q²")
                hist.update_layout(
                    template="plotly_white",
                    xaxis_title="Permuted Q²",
                    title="Y-randomization test",
                )
                st.plotly_chart(hist, width="stretch")
            except Exception as exc:
                st.error(str(exc))

    with vart:
        st.warning(
            "VIP thresholding and iPLS below are wavelength-screening tools. Selecting variables/intervals and then "
            "reporting performance from the same CV loop is optimistically biased. Final model assessment must repeat "
            "selection inside nested CV or use a locked independent test set."
        )
        v1, v2 = st.tabs(["VIP threshold", "Interval PLS (iPLS)"])
        with v1:
            nc = st.number_input(
                "PLS components for VIP",
                1,
                max(1, min(15, len(Xg) - 1, Xg.shape[1])),
                min(3, max(1, min(15, len(Xg) - 1, Xg.shape[1]))),
                key="chem_adv_vip_nc",
            )
            threshold = st.number_input("VIP threshold", 0.0, 10.0, 1.0, 0.05)
            try:
                vip_result = pls_with_vip(Xg, yg, int(nc))
                selection = vip_threshold_select(vip_result["vip"], wl, threshold)
                st.write(f"Selected wavelengths: **{len(selection['indices'])} / {len(wl)}**")
                vip_figure = go.Figure(go.Scatter(x=wl, y=vip_result["vip"], mode="lines"))
                vip_figure.add_hline(y=threshold, line_dash="dash")
                vip_figure.update_layout(
                    template="plotly_white",
                    xaxis_title="Wavelength (nm)",
                    yaxis_title="VIP",
                    title="VIP wavelength screening",
                )
                st.plotly_chart(vip_figure, width="stretch")
                st.dataframe(
                    pd.DataFrame({"Wavelength (nm)": selection["wavelengths"], "VIP": selection["vip"]})
                    .sort_values("VIP", ascending=False)
                    .head(100),
                    width="stretch",
                    hide_index=True,
                )
            except Exception as exc:
                st.error(str(exc))
        with v2:
            c1, c2, c3 = st.columns(3)
            intervals = c1.number_input(
                "Intervals", 2, min(50, Xg.shape[1]), min(10, max(2, Xg.shape[1] // 10))
            )
            nc = c2.number_input(
                "PLS components",
                1,
                max(1, min(10, len(Xg) - 1)),
                min(3, max(1, min(10, len(Xg) - 1))),
                key="chem_ipls_nc",
            )
            cv = c3.number_input("CV folds", 2, len(Xg), min(5, len(Xg)), key="chem_ipls_cv")
            try:
                result = interval_pls(Xg, yg, wl, int(intervals), int(nc), int(cv))
                table = pd.DataFrame(
                    [{k: v for k, v in row.items() if k != "indices"} for row in result["results"]]
                ).sort_values("rmsecv")
                st.dataframe(table, width="stretch", hide_index=True)
                best = result["best"]
                st.success(
                    f"Screening-best interval: {best['start_nm']:.2f}–{best['end_nm']:.2f} nm · "
                    f"RMSECV={best['rmsecv']:.6g} · Q²={best['q2']:.5f}"
                )
                st.warning(result["selection_warning"])
            except Exception as exc:
                st.error(str(exc))
