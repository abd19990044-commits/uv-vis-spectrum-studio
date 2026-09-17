from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats
from scipy.stats import linregress


@dataclass
class LinearCalibrationResult:
    slope: float
    intercept: float
    r2: float
    syx: float
    lod: float | None
    loq: float | None
    epsilon_L_mol_cm: float | None
    predicted: np.ndarray
    residuals: np.ndarray


@dataclass
class WeightedCalibrationResult:
    """Weighted least-squares result for analytical calibration.

    ``weighting`` is one of ``1/x``, ``1/x^2``, ``1/y``, ``1/y^2`` or
    ``custom``. Reciprocal schemes deliberately reject zero/non-positive
    denominators rather than silently regularising them, because an arbitrary
    epsilon would change the statistical model.

    References
    ----------
    See ``REFERENCES.md`` for the weighted-regression and analytical-
    calibration references used by this project.
    """

    slope: float
    intercept: float
    r2: float
    weighted_r2: float
    rmse: float
    weighted_residual_se: float
    predicted: np.ndarray
    residuals: np.ndarray
    weights: np.ndarray
    weighting: str
    weighted_sse: float
    degrees_of_freedom: int


def _finite_xy(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    m = np.isfinite(x) & np.isfinite(y)
    return x[m], y[m]


def linear_calibration(
    concentration,
    response,
    *,
    sigma: float | None = None,
    molecular_weight_g_mol: float | None = None,
    path_length_cm: float = 1.0,
    concentration_unit: str = "µg/mL",
) -> LinearCalibrationResult:
    x, y = _finite_xy(concentration, response)
    if len(x) < 3:
        raise ValueError("At least three calibration points are required.")
    if np.ptp(x) == 0:
        raise ValueError("Calibration concentrations must not all be identical.")

    fit = linregress(x, y)
    predicted = fit.intercept + fit.slope * x
    residuals = y - predicted
    syx = float(np.sqrt(np.sum(residuals**2) / max(len(x) - 2, 1)))
    sigma_use = syx if sigma is None else abs(float(sigma))
    lod = 3.3 * sigma_use / abs(fit.slope) if fit.slope != 0 else None
    loq = 10.0 * sigma_use / abs(fit.slope) if fit.slope != 0 else None

    epsilon = None
    l = float(path_length_cm)
    if molecular_weight_g_mol and molecular_weight_g_mol > 0 and l > 0:
        mw = float(molecular_weight_g_mol)
        if concentration_unit in {"µg/mL", "mg/L"}:
            epsilon = float((fit.slope * mw / 0.001) / l)
        elif concentration_unit == "mol/L":
            epsilon = float(fit.slope / l)
        elif concentration_unit == "mmol/L":
            epsilon = float(fit.slope * 1000.0 / l)

    return LinearCalibrationResult(
        float(fit.slope),
        float(fit.intercept),
        float(fit.rvalue**2),
        syx,
        float(lod) if lod is not None else None,
        float(loq) if loq is not None else None,
        epsilon,
        predicted,
        residuals,
    )


def _calibration_weights(x, y, weighting: str, custom_weights=None) -> np.ndarray:
    scheme = str(weighting).strip().lower().replace("²", "^2").replace(" ", "")
    aliases = {
        "1/x": "1/x",
        "1/x^2": "1/x^2",
        "1/y": "1/y",
        "1/y^2": "1/y^2",
        "custom": "custom",
    }
    if scheme not in aliases:
        raise ValueError("weighting must be one of: 1/x, 1/x^2, 1/y, 1/y^2, custom.")

    if scheme == "custom":
        if custom_weights is None:
            raise ValueError("custom_weights are required when weighting='custom'.")
        w = np.asarray(custom_weights, dtype=float).reshape(-1)
        if w.size != x.size:
            raise ValueError("custom_weights must contain one value per calibration observation.")
    else:
        base = x if "x" in scheme else y
        if np.any(~np.isfinite(base)) or np.any(base <= 0):
            axis = "concentrations" if "x" in scheme else "responses"
            raise ValueError(
                f"{scheme} weighting requires strictly positive finite {axis}; "
                "zero standards/responses cannot be assigned reciprocal weights."
            )
        power = 2 if "^2" in scheme else 1
        w = 1.0 / np.power(base, power)

    if np.any(~np.isfinite(w)) or np.any(w <= 0):
        raise ValueError("All calibration weights must be positive and finite.")

    # Scale by the mean so the numerical magnitude of the objective is stable;
    # multiplying all WLS weights by one constant does not change beta.
    return w / float(np.mean(w))


def weighted_linear_calibration(
    concentration,
    response,
    *,
    weighting: str = "1/x",
    custom_weights=None,
) -> WeightedCalibrationResult:
    """Fit a two-parameter weighted least-squares calibration line.

    This function is intended for calibration ranges where response variance is
    demonstrably concentration-dependent. Choice of weights must be justified
    from residual/error behaviour; it should not be selected merely because it
    improves R².

    The reported ``weighted_residual_se`` is sqrt(sum(w*r²)/(n-2)). Because
    reciprocal weights may carry an implicit scale, it is *not* substituted
    automatically as the response sigma for LOD/LOQ calculations.
    """
    x, y = _finite_xy(concentration, response)
    if len(x) < 3:
        raise ValueError("At least three calibration points are required.")
    if np.ptp(x) == 0:
        raise ValueError("Calibration concentrations must not all be identical.")

    if custom_weights is not None:
        raw_w = np.asarray(custom_weights, dtype=float).reshape(-1)
        raw_x = np.asarray(concentration, dtype=float).reshape(-1)
        raw_y = np.asarray(response, dtype=float).reshape(-1)
        if not (raw_x.size == raw_y.size == raw_w.size):
            raise ValueError("concentration, response and custom_weights must have equal length.")
        mask = np.isfinite(raw_x) & np.isfinite(raw_y) & np.isfinite(raw_w)
        x, y, custom_weights = raw_x[mask], raw_y[mask], raw_w[mask]

    w = _calibration_weights(x, y, weighting, custom_weights=custom_weights)
    X = np.column_stack([np.ones(len(x)), x])
    xtwx = X.T @ (w[:, None] * X)
    if np.linalg.cond(xtwx) > 1e14:
        raise ValueError("Weighted calibration design matrix is numerically ill-conditioned.")

    beta = np.linalg.solve(xtwx, X.T @ (w * y))
    predicted = X @ beta
    residuals = y - predicted
    dof = len(x) - 2
    weighted_sse = float(np.sum(w * residuals**2))
    wrse = float(np.sqrt(weighted_sse / dof))
    rmse = float(np.sqrt(np.mean(residuals**2)))

    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    ss_res = float(np.sum(residuals**2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0
    y_wmean = float(np.average(y, weights=w))
    wss_tot = float(np.sum(w * (y - y_wmean) ** 2))
    weighted_r2 = 1.0 - weighted_sse / wss_tot if wss_tot > 0 else 1.0

    return WeightedCalibrationResult(
        slope=float(beta[1]),
        intercept=float(beta[0]),
        r2=float(r2),
        weighted_r2=float(weighted_r2),
        rmse=rmse,
        weighted_residual_se=wrse,
        predicted=predicted,
        residuals=residuals,
        weights=w,
        weighting=str(weighting),
        weighted_sse=weighted_sse,
        degrees_of_freedom=int(dof),
    )


def breusch_pagan_calibration_test(concentration, response) -> dict:
    """Breusch-Pagan diagnostic for concentration-dependent residual variance.

    The primary calibration is ordinary least squares. Squared OLS residuals
    are regressed on concentration (with an intercept); LM = n*R² and is
    compared with chi-square(1). This is a diagnostic, not an automatic rule
    for choosing a weighting function.
    """
    x, y = _finite_xy(concentration, response)
    if len(x) < 5:
        raise ValueError("Breusch-Pagan calibration diagnostic requires at least five observations.")
    if np.ptp(x) == 0:
        raise ValueError("Calibration concentrations must not all be identical.")

    fit = linear_calibration(x, y)
    e2 = np.asarray(fit.residuals, dtype=float) ** 2
    Z = np.column_stack([np.ones(len(x)), x])
    gamma = np.linalg.lstsq(Z, e2, rcond=None)[0]
    fitted_e2 = Z @ gamma
    ss_tot = float(np.sum((e2 - np.mean(e2)) ** 2))
    ss_res = float(np.sum((e2 - fitted_e2) ** 2))
    aux_r2 = 0.0 if ss_tot <= np.finfo(float).eps else max(0.0, 1.0 - ss_res / ss_tot)
    lm = float(len(x) * aux_r2)
    p_value = float(stats.chi2.sf(lm, 1))
    rho, rho_p = stats.spearmanr(np.abs(fit.residuals), fit.predicted)

    return {
        "lm": lm,
        "degrees_of_freedom": 1,
        "p_value": p_value,
        "auxiliary_r2": float(aux_r2),
        "heteroscedastic_at_0_05": bool(p_value < 0.05),
        "spearman_abs_residual_vs_fitted": float(rho),
        "spearman_p_value": float(rho_p),
        "residuals": fit.residuals,
        "predicted": fit.predicted,
    }


def standard_addition(added_concentration, response, dilution_factor: float = 1.0) -> dict:
    x, y = _finite_xy(added_concentration, response)
    if len(x) < 3:
        raise ValueError("At least three standard-addition points are required.")
    fit = linregress(x, y)
    if fit.slope == 0:
        raise ValueError("Standard-addition slope is zero.")
    x_intercept = -fit.intercept / fit.slope
    predicted = fit.intercept + fit.slope * x
    return {
        "slope": float(fit.slope),
        "intercept": float(fit.intercept),
        "r2": float(fit.rvalue**2),
        "x_intercept": float(x_intercept),
        "sample_concentration_final": float(-x_intercept),
        "sample_concentration_original": float(-x_intercept * dilution_factor),
        "predicted": predicted,
        "residuals": y - predicted,
    }


def job_method(mole_fraction_a, response) -> dict:
    x, y = _finite_xy(mole_fraction_a, response)
    if len(x) < 3:
        raise ValueError("At least three Job-method points are required.")
    o = np.argsort(x)
    x, y = x[o], y[o]
    i = int(np.argmax(y))
    x_peak = float(x[i])
    if 0 < i < len(x) - 1:
        xx, yy = x[i - 1 : i + 2], y[i - 1 : i + 2]
        c = np.polyfit(xx, yy, 2)
        if c[0] != 0:
            xv = -c[1] / (2 * c[0])
            if xx[0] <= xv <= xx[-1]:
                x_peak = float(xv)
    ratio = x_peak / (1 - x_peak) if 0 < x_peak < 1 else float("nan")
    return {"x_peak": x_peak, "ratio_a_to_b": float(ratio), "x": x, "y": y}


def mole_ratio_method(reagent_to_analyte_ratio, response, min_segment_points: int = 2) -> dict:
    x, y = _finite_xy(reagent_to_analyte_ratio, response)
    o = np.argsort(x)
    x, y = x[o], y[o]
    if len(x) < max(6, 2 * min_segment_points + 1):
        raise ValueError("At least six mole-ratio points are recommended.")
    best = None
    for k in range(min_segment_points, len(x) - min_segment_points):
        f1 = linregress(x[: k + 1], y[: k + 1])
        f2 = linregress(x[k:], y[k:])
        sse = float(
            np.sum((y[: k + 1] - (f1.intercept + f1.slope * x[: k + 1])) ** 2)
            + np.sum((y[k:] - (f2.intercept + f2.slope * x[k:])) ** 2)
        )
        den = f1.slope - f2.slope
        if abs(den) < 1e-15:
            continue
        xi = (f2.intercept - f1.intercept) / den
        if best is None or sse < best[0]:
            best = (sse, xi, f1, f2)
    if best is None:
        raise ValueError("Could not determine segmented-regression breakpoint.")
    _, bp, f1, f2 = best
    return {
        "breakpoint_ratio": float(bp),
        "slope1": float(f1.slope),
        "intercept1": float(f1.intercept),
        "r2_1": float(f1.rvalue**2),
        "slope2": float(f2.slope),
        "intercept2": float(f2.intercept),
        "r2_2": float(f2.rvalue**2),
        "x": x,
        "y": y,
    }


def isosbestic_points(x1, y1, x2, y2, tolerance: float | None = None) -> list[dict[str, float]]:
    x1, y1 = _finite_xy(x1, y1)
    x2, y2 = _finite_xy(x2, y2)
    if len(x1) < 2 or len(x2) < 2:
        return []
    o1, o2 = np.argsort(x1), np.argsort(x2)
    x1, y1, x2, y2 = x1[o1], y1[o1], x2[o2], y2[o2]
    lo, hi = max(np.min(x1), np.min(x2)), min(np.max(x1), np.max(x2))
    if hi <= lo:
        return []
    x = x1[(x1 >= lo) & (x1 <= hi)]
    if len(x) < 2:
        return []
    a, b = np.interp(x, x1, y1), np.interp(x, x2, y2)
    d = a - b
    tol = abs(float(tolerance)) if tolerance is not None else max(np.ptp(np.r_[a, b]) * 1e-8, 1e-12)
    rows = []
    for i in range(len(x) - 1):
        d1, d2 = d[i], d[i + 1]
        if abs(d1) <= tol:
            xc = float(x[i])
        elif d1 * d2 < 0:
            xc = float(x[i] - d1 * (x[i + 1] - x[i]) / (d2 - d1))
        else:
            continue
        yc = float(np.interp(xc, x, (a + b) / 2))
        if not rows or abs(rows[-1]["wavelength_nm"] - xc) > 1e-6:
            rows.append({"wavelength_nm": xc, "signal": yc})
    return rows
