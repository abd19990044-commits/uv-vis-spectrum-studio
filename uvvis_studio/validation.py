from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats

from .quantitation import calculate_molar_absorptivity


@dataclass
class LinearityValidation:
    slope: float
    intercept: float
    r2: float
    syx: float
    slope_se: float
    intercept_se: float
    slope_ci95: tuple[float, float]
    intercept_ci95: tuple[float, float]
    residuals: np.ndarray
    predicted: np.ndarray
    lod_33: float | None
    loq_10: float | None
    epsilon_L_mol_cm: float | None = None


def _clean_xy(x, y) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(x, dtype=float).reshape(-1)
    y = np.asarray(y, dtype=float).reshape(-1)
    if x.size != y.size:
        raise ValueError("x and y must contain the same number of observations.")
    mask = np.isfinite(x) & np.isfinite(y)
    return x[mask], y[mask]


def linearity_validation(
    x,
    y,
    sigma: float | None = None,
    *,
    molecular_weight_g_mol: float | None = None,
    path_length_cm: float = 1.0,
    concentration_unit: str = "µg/mL",
) -> LinearityValidation:
    """Ordinary least-squares linearity statistics for analytical calibration.

    LOD and LOQ use 3.3*sigma/|S| and 10*sigma/|S|, respectively.  When
    ``sigma`` is omitted, Sy/x is used as an exploratory estimate.  Regulatory
    use still requires the analyst to choose and document the sigma source
    appropriate to the validated procedure.
    """
    x, y = _clean_xy(x, y)
    if len(x) < 3 or np.ptp(x) <= 0:
        raise ValueError(
            "At least three finite calibration levels with non-zero concentration range are required."
        )

    # Center the calculation so a change from µg/mL to mol/L does not
    # create an artificial condition-number failure in the intercept column.
    dx = x - np.mean(x)
    sxx = float(dx @ dx)
    slope = float(dx @ (y - np.mean(y)) / sxx)
    beta = np.array([np.mean(y) - slope * np.mean(x), slope])
    predicted = np.mean(y) + slope * dx
    residuals = y - predicted
    dof = len(x) - 2
    syx = float(np.sqrt(np.sum(residuals**2) / dof))

    slope_se = syx / np.sqrt(sxx)
    intercept_se = syx * np.sqrt(1.0 / len(x) + np.mean(x)**2 / sxx)
    tcrit = float(stats.t.ppf(0.975, dof))

    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    ss_res = float(np.sum(residuals**2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")

    sigma_use = syx if sigma is None else float(sigma)
    if not np.isfinite(sigma_use) or sigma_use < 0:
        raise ValueError("sigma must be finite and nonnegative.")
    slope = float(beta[1])
    abs_slope = abs(slope)
    lod = 3.3 * sigma_use / abs_slope if abs_slope > 0 else None
    loq = 10.0 * sigma_use / abs_slope if abs_slope > 0 else None

    epsilon = calculate_molar_absorptivity(
        slope,
        path_length_cm=path_length_cm,
        molecular_weight_g_mol=molecular_weight_g_mol,
        concentration_unit=concentration_unit,
    )

    intercept = float(beta[0])
    return LinearityValidation(
        slope=slope,
        intercept=intercept,
        r2=float(r2),
        syx=syx,
        slope_se=float(slope_se),
        intercept_se=float(intercept_se),
        slope_ci95=(float(slope - tcrit * slope_se), float(slope + tcrit * slope_se)),
        intercept_ci95=(
            float(intercept - tcrit * intercept_se),
            float(intercept + tcrit * intercept_se),
        ),
        residuals=residuals,
        predicted=predicted,
        lod_33=float(lod) if lod is not None else None,
        loq_10=float(loq) if loq is not None else None,
        epsilon_L_mol_cm=epsilon,
    )


def mandel_fitting_test(x, y, alpha: float = 0.05) -> dict:
    """Mandel fitting test comparing first- and second-order calibration models.

    A significant F test indicates that the quadratic model reduces residual
    variance beyond what is expected from adding one model parameter.  This is
    a model-comparison diagnostic, not by itself proof that a quadratic
    calibration is analytically appropriate.
    """
    x, y = _clean_xy(x, y)
    if len(x) < 4 or np.ptp(x) <= 0:
        raise ValueError("Mandel's fitting test requires at least four finite calibration observations.")
    if not 0 < float(alpha) < 1:
        raise ValueError("alpha must be between 0 and 1.")

    if np.unique(x).size < 3:
        raise ValueError("A quadratic comparison needs at least three distinct concentrations.")
    line = np.polynomial.Polynomial.fit(x, y, 1)
    quadratic = np.polynomial.Polynomial.fit(x, y, 2)
    p1 = line.convert().coef[::-1]
    p2 = quadratic.convert().coef[::-1]
    r1 = y - line(x)
    r2 = y - quadratic(x)
    ss1 = float(np.sum(r1**2))
    ss2 = float(np.sum(r2**2))
    df2 = len(x) - 3
    if df2 <= 0:
        raise ValueError("Insufficient residual degrees of freedom for Mandel's fitting test.")

    improvement = max(ss1 - ss2, 0.0)
    roundoff_ss = 100 * len(y) * np.finfo(float).eps**2 * float(y @ y)
    if ss2 <= roundoff_ss:
        f_value = float("inf") if improvement > roundoff_ss else float("nan")
    else:
        f_value = float(improvement / (ss2 / df2))
    p_value = float(stats.f.sf(f_value, 1, df2))
    f_critical = float(stats.f.ppf(1.0 - float(alpha), 1, df2))

    return {
        "ss_linear": ss1,
        "ss_quadratic": ss2,
        "df_numerator": 1,
        "df_denominator": int(df2),
        "f": f_value,
        "f_critical": f_critical,
        "p_value": p_value,
        "alpha": float(alpha),
        "quadratic_improvement_significant": bool(p_value < float(alpha)),
        "linear_coefficients": p1,
        "quadratic_coefficients": p2,
        "linear_residuals": r1,
        "quadratic_residuals": r2,
    }


def inverse_prediction_interval(
    concentration,
    response,
    unknown_response: float,
    *,
    unknown_replicates: int = 1,
    confidence: float = 0.95,
) -> dict:
    """Inverse linear-calibration estimate and approximate confidence interval.

    The interval follows the classical inverse-prediction standard error for a
    mean unknown response based on ``unknown_replicates`` independent readings.
    It assumes the same homoscedastic linear model used for the calibration.
    """
    x, y = _clean_xy(concentration, response)
    if len(x) < 3 or np.ptp(x) <= 0:
        raise ValueError("At least three valid calibration observations are required.")
    m = int(unknown_replicates)
    if m < 1:
        raise ValueError("unknown_replicates must be at least 1.")
    if not 0 < float(confidence) < 1:
        raise ValueError("confidence must be between 0 and 1.")

    fit = linearity_validation(x, y)
    if not np.isfinite(fit.slope) or fit.slope == 0:
        raise ValueError("A finite nonzero calibration slope is required for inverse prediction.")

    y0 = float(unknown_response)
    if not np.isfinite(y0):
        raise ValueError("unknown_response must be finite.")
    xhat = (y0 - fit.intercept) / fit.slope
    xbar = float(np.mean(x))
    sxx = float(np.sum((x - xbar) ** 2))
    if sxx <= 0:
        raise ValueError("Calibration concentrations have zero variance.")

    se_x = fit.syx / abs(fit.slope) * np.sqrt(
        1.0 / m + 1.0 / len(x) + ((xhat - xbar) ** 2) / sxx
    )
    dof = len(x) - 2
    tcrit = float(stats.t.ppf((1.0 + float(confidence)) / 2.0, dof))
    half_width = float(tcrit * se_x)
    return {
        "concentration": float(xhat),
        "standard_error": float(se_x),
        "confidence": float(confidence),
        "lower": float(xhat - half_width),
        "upper": float(xhat + half_width),
        "degrees_of_freedom": int(dof),
        "unknown_replicates": m,
    }


def precision_summary(values, reference: float | None = None) -> dict:
    a = np.asarray(values, dtype=float)
    a = a[np.isfinite(a)]
    if len(a) < 2:
        raise ValueError("At least two replicate results are required.")
    mean = float(np.mean(a))
    sd = float(np.std(a, ddof=1))
    rsd = 100 * sd / abs(mean) if mean else np.nan
    out = {
        "n": len(a),
        "mean": mean,
        "sd": sd,
        "rsd_percent": rsd,
        "min": float(np.min(a)),
        "max": float(np.max(a)),
    }
    if reference is not None and float(reference) != 0:
        out["recovery_percent"] = 100 * mean / float(reference)
        out["bias_percent"] = 100 * (mean - float(reference)) / float(reference)
    return out


def recovery_summary(found, nominal) -> dict:
    f = np.asarray(found, dtype=float)
    n = np.asarray(nominal, dtype=float)
    if f.size != n.size:
        raise ValueError("found and nominal must contain the same number of observations.")
    mask = np.isfinite(f) & np.isfinite(n) & (n != 0)
    f, n = f[mask], n[mask]
    if len(f) < 2:
        raise ValueError("At least two valid recovery pairs are required.")
    recovery = 100 * f / n
    mean_recovery = float(np.mean(recovery))
    sd = float(np.std(recovery, ddof=1))
    return {
        "recovery_percent": recovery,
        "mean_recovery_percent": mean_recovery,
        "sd": sd,
        "rsd_percent": float(100 * sd / abs(mean_recovery)) if mean_recovery else np.nan,
    }


def robustness_summary(values, factors=None) -> dict:
    a = np.asarray(values, dtype=float)
    a = a[np.isfinite(a)]
    if len(a) < 2:
        raise ValueError("At least two robustness results are required.")
    mean = float(np.mean(a))
    sd = float(np.std(a, ddof=1))
    result = {
        "mean": mean,
        "sd": sd,
        "rsd_percent": 100 * sd / abs(mean) if mean else np.nan,
        "range": float(np.ptp(a)),
    }
    if factors is not None:
        result["factors"] = list(factors)
    return result


def lack_of_fit_test(concentration, response) -> dict:
    x, y = _clean_xy(concentration, response)
    levels = np.unique(x)
    if len(levels) < 3 or len(x) <= len(levels):
        raise ValueError(
            "Lack-of-fit requires replicated responses at at least three concentration levels."
        )
    fit = linearity_validation(x, y)
    ss_res = float(np.sum(fit.residuals**2))
    ss_pe = 0.0
    df_pe = 0
    for level in levels:
        values = y[x == level]
        if len(values) > 1:
            ss_pe += float(np.sum((values - np.mean(values)) ** 2))
            df_pe += len(values) - 1
    df_lof = (len(x) - 2) - df_pe
    if df_pe <= 0 or df_lof <= 0:
        raise ValueError("Insufficient replicated data for lack-of-fit partitioning.")
    ss_lof = max(ss_res - ss_pe, 0.0)
    # No estimated pure-error variance means the F test is not estimable.
    # Report unavailable, not p=0 (a false claim of significant lack of fit).
    f_value = (ss_lof / df_lof) / (ss_pe / df_pe) if ss_pe > 0 else float("nan")
    p_value = float(stats.f.sf(f_value, df_lof, df_pe))
    return {
        "status": "ok" if ss_pe > 0 else "undefined_zero_pure_error",
        "ss_pure_error": ss_pe,
        "ss_lack_of_fit": ss_lof,
        "df_pure_error": df_pe,
        "df_lack_of_fit": df_lof,
        "f": float(f_value),
        "p_value": p_value,
    }
