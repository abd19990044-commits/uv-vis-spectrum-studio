from __future__ import annotations

from dataclasses import dataclass
import numpy as np
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


def _finite_xy(x, y):
    x = np.asarray(x, dtype=float); y = np.asarray(y, dtype=float)
    m = np.isfinite(x) & np.isfinite(y)
    return x[m], y[m]


def linear_calibration(concentration, response, *, sigma: float | None = None, molecular_weight_g_mol: float | None = None, path_length_cm: float = 1.0, concentration_unit: str = "µg/mL") -> LinearCalibrationResult:
    x, y = _finite_xy(concentration, response)
    if len(x) < 3: raise ValueError("At least three calibration points are required.")
    if np.ptp(x) == 0: raise ValueError("Calibration concentrations must not all be identical.")
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
    return LinearCalibrationResult(float(fit.slope), float(fit.intercept), float(fit.rvalue**2), syx, float(lod) if lod is not None else None, float(loq) if loq is not None else None, epsilon, predicted, residuals)


def standard_addition(added_concentration, response, dilution_factor: float = 1.0) -> dict:
    x, y = _finite_xy(added_concentration, response)
    if len(x) < 3: raise ValueError("At least three standard-addition points are required.")
    fit = linregress(x, y)
    if fit.slope == 0: raise ValueError("Standard-addition slope is zero.")
    x_intercept = -fit.intercept / fit.slope
    predicted = fit.intercept + fit.slope * x
    return {"slope": float(fit.slope), "intercept": float(fit.intercept), "r2": float(fit.rvalue**2), "x_intercept": float(x_intercept), "sample_concentration_final": float(-x_intercept), "sample_concentration_original": float(-x_intercept * dilution_factor), "predicted": predicted, "residuals": y - predicted}


def job_method(mole_fraction_a, response) -> dict:
    x, y = _finite_xy(mole_fraction_a, response)
    if len(x) < 3: raise ValueError("At least three Job-method points are required.")
    o = np.argsort(x); x, y = x[o], y[o]
    i = int(np.argmax(y)); x_peak = float(x[i])
    if 0 < i < len(x)-1:
        xx, yy = x[i-1:i+2], y[i-1:i+2]
        c = np.polyfit(xx, yy, 2)
        if c[0] != 0:
            xv = -c[1]/(2*c[0])
            if xx[0] <= xv <= xx[-1]: x_peak = float(xv)
    ratio = x_peak/(1-x_peak) if 0 < x_peak < 1 else float("nan")
    return {"x_peak": x_peak, "ratio_a_to_b": float(ratio), "x": x, "y": y}


def mole_ratio_method(reagent_to_analyte_ratio, response, min_segment_points: int = 2) -> dict:
    x, y = _finite_xy(reagent_to_analyte_ratio, response)
    o = np.argsort(x); x, y = x[o], y[o]
    if len(x) < max(6, 2*min_segment_points+1): raise ValueError("At least six mole-ratio points are recommended.")
    best = None
    for k in range(min_segment_points, len(x)-min_segment_points):
        f1 = linregress(x[:k+1], y[:k+1]); f2 = linregress(x[k:], y[k:])
        sse = float(np.sum((y[:k+1]-(f1.intercept+f1.slope*x[:k+1]))**2) + np.sum((y[k:]-(f2.intercept+f2.slope*x[k:]))**2))
        den = f1.slope - f2.slope
        if abs(den) < 1e-15: continue
        xi = (f2.intercept-f1.intercept)/den
        if best is None or sse < best[0]: best = (sse, xi, f1, f2)
    if best is None: raise ValueError("Could not determine segmented-regression breakpoint.")
    _, bp, f1, f2 = best
    return {"breakpoint_ratio": float(bp), "slope1": float(f1.slope), "intercept1": float(f1.intercept), "r2_1": float(f1.rvalue**2), "slope2": float(f2.slope), "intercept2": float(f2.intercept), "r2_2": float(f2.rvalue**2), "x": x, "y": y}


def isosbestic_points(x1, y1, x2, y2, tolerance: float | None = None) -> list[dict[str, float]]:
    x1, y1 = _finite_xy(x1, y1); x2, y2 = _finite_xy(x2, y2)
    if len(x1) < 2 or len(x2) < 2: return []
    o1, o2 = np.argsort(x1), np.argsort(x2); x1, y1, x2, y2 = x1[o1], y1[o1], x2[o2], y2[o2]
    lo, hi = max(np.min(x1), np.min(x2)), min(np.max(x1), np.max(x2))
    if hi <= lo: return []
    x = x1[(x1 >= lo) & (x1 <= hi)]
    if len(x) < 2: return []
    a, b = np.interp(x, x1, y1), np.interp(x, x2, y2); d = a-b
    tol = abs(float(tolerance)) if tolerance is not None else max(np.ptp(np.r_[a,b])*1e-8, 1e-12)
    rows = []
    for i in range(len(x)-1):
        d1, d2 = d[i], d[i+1]
        if abs(d1) <= tol: xc = float(x[i])
        elif d1*d2 < 0: xc = float(x[i] - d1*(x[i+1]-x[i])/(d2-d1))
        else: continue
        yc = float(np.interp(xc, x, (a+b)/2))
        if not rows or abs(rows[-1]["wavelength_nm"]-xc) > 1e-6: rows.append({"wavelength_nm": xc, "signal": yc})
    return rows
