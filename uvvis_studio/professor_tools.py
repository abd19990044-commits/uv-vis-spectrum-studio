from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import numpy as np
import pywt
from scipy import signal
from scipy.integrate import trapezoid
from sklearn.cross_decomposition import PLSRegression
from sklearn.decomposition import PCA
from sklearn.metrics import mean_squared_error, r2_score


@dataclass
class RegressionResult:
    slope: float
    intercept: float
    r_squared: float
    adjusted_r_squared: float
    rmse: float
    syx: float
    slope_se: float
    intercept_se: float
    n: int
    predicted: np.ndarray
    residuals: np.ndarray
    lod: float | None = None
    loq: float | None = None
    epsilon: float | None = None


def _clean_xy(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    if len(x) < 2:
        raise ValueError("At least two finite points are required.")
    order = np.argsort(x)
    return x[order], y[order]


def linear_regression(x, y, sigma: float | None = None, *, molecular_weight: float | None = None,
                      path_length_cm: float = 1.0, concentration_unit: str = "µg/mL") -> RegressionResult:
    x, y = _clean_xy(x, y)
    if np.ptp(x) == 0:
        raise ValueError("X values must not all be identical.")
    n = len(x)
    slope, intercept = np.polyfit(x, y, 1)
    predicted = slope * x + intercept
    residuals = y - predicted
    ss_res = float(np.sum(residuals ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0
    rmse = float(np.sqrt(np.mean(residuals ** 2)))
    syx = float(np.sqrt(ss_res / max(n - 2, 1)))
    sxx = float(np.sum((x - np.mean(x)) ** 2))
    slope_se = syx / np.sqrt(sxx) if sxx > 0 else float("nan")
    intercept_se = syx * np.sqrt(1.0 / n + (np.mean(x) ** 2) / sxx) if sxx > 0 else float("nan")
    adj_r2 = 1.0 - (1.0 - r2) * (n - 1) / max(n - 2, 1)

    lod = loq = None
    if sigma is not None and np.isfinite(sigma) and sigma >= 0 and slope != 0:
        lod = float(3.3 * sigma / abs(slope))
        loq = float(10.0 * sigma / abs(slope))

    epsilon = None
    if slope != 0 and path_length_cm > 0:
        factor_to_molar = None
        if concentration_unit == "mol/L":
            factor_to_molar = 1.0
        elif concentration_unit == "mmol/L":
            factor_to_molar = 1e-3
        elif concentration_unit == "µmol/L":
            factor_to_molar = 1e-6
        elif concentration_unit in {"µg/mL", "mg/L"} and molecular_weight and molecular_weight > 0:
            factor_to_molar = 1e-3 / molecular_weight
        elif concentration_unit == "mg/mL" and molecular_weight and molecular_weight > 0:
            factor_to_molar = 1.0 / molecular_weight
        if factor_to_molar:
            epsilon = float(slope / (path_length_cm * factor_to_molar))

    return RegressionResult(
        slope=float(slope), intercept=float(intercept), r_squared=float(r2),
        adjusted_r_squared=float(adj_r2), rmse=rmse, syx=syx,
        slope_se=float(slope_se), intercept_se=float(intercept_se), n=n,
        predicted=predicted, residuals=residuals, lod=lod, loq=loq, epsilon=epsilon,
    )


def standard_addition(added_concentration, signal_values, dilution_factor: float = 1.0) -> dict:
    x, y = _clean_xy(added_concentration, signal_values)
    fit = linear_regression(x, y)
    if fit.slope == 0:
        raise ValueError("Standard-addition slope is zero.")
    x_intercept = -fit.intercept / fit.slope
    original = abs(float(x_intercept)) * float(dilution_factor)
    return {"fit": fit, "x_intercept": float(x_intercept), "original_concentration": original}


def jobs_method(mole_fraction_analyte, signal_values) -> dict:
    x, y = _clean_xy(mole_fraction_analyte, signal_values)
    if np.any((x < 0) | (x > 1)):
        raise ValueError("Job mole fractions must be between 0 and 1.")
    idx = int(np.nanargmax(y))
    xmax = float(x[idx])
    if xmax <= 0 or xmax >= 1:
        ratio_text = "Undetermined"
        ratio = float("nan")
    else:
        ratio = xmax / (1 - xmax)
        f = Fraction(ratio).limit_denominator(8)
        ratio_text = f"{f.numerator}:{f.denominator}"
    return {"x_max": xmax, "signal_max": float(y[idx]), "analyte_to_reagent_ratio": ratio,
            "nearest_integer_ratio": ratio_text}


def mole_ratio_method(ratio_reagent_to_analyte, signal_values) -> dict:
    x, y = _clean_xy(ratio_reagent_to_analyte, signal_values)
    if len(x) < 5:
        raise ValueError("At least five mole-ratio points are recommended for breakpoint fitting.")
    best = None
    for split in range(2, len(x) - 2):
        c1 = np.polyfit(x[:split + 1], y[:split + 1], 1)
        c2 = np.polyfit(x[split:], y[split:], 1)
        p1 = np.polyval(c1, x[:split + 1])
        p2 = np.polyval(c2, x[split:])
        sse = float(np.sum((y[:split + 1] - p1) ** 2) + np.sum((y[split:] - p2) ** 2))
        den = c1[0] - c2[0]
        if abs(den) < 1e-15:
            continue
        xb = float((c2[1] - c1[1]) / den)
        if x[0] <= xb <= x[-1]:
            item = (sse, xb, c1, c2, split)
            if best is None or sse < best[0]:
                best = item
    if best is None:
        raise ValueError("A stable two-line breakpoint could not be determined.")
    _, xb, c1, c2, split = best
    f = Fraction(max(xb, 0)).limit_denominator(8)
    return {"breakpoint_ratio": xb, "nearest_integer_ratio": f"{f.numerator}:{f.denominator}",
            "line1_slope": float(c1[0]), "line1_intercept": float(c1[1]),
            "line2_slope": float(c2[0]), "line2_intercept": float(c2[1]), "split_index": int(split)}


def fft_spectrum(x, y, *, detrend: str = "linear", window: str = "hann") -> dict:
    x, y = _clean_xy(x, y)
    if len(x) < 4:
        raise ValueError("At least four spectral points are required for FFT.")
    dx = float(np.median(np.diff(x)))
    uniform_x = np.arange(x[0], x[-1] + dx * 0.5, dx)
    yy = np.interp(uniform_x, x, y)
    if detrend in {"linear", "constant"}:
        yy = signal.detrend(yy, type=detrend)
    if window == "hann":
        yy = yy * np.hanning(len(yy))
    elif window == "hamming":
        yy = yy * np.hamming(len(yy))
    spec = np.fft.rfft(yy)
    freq = np.fft.rfftfreq(len(yy), d=dx)
    amp = 2.0 * np.abs(spec) / len(yy)
    phase = np.angle(spec)
    period = np.divide(1.0, freq, out=np.full_like(freq, np.inf), where=freq > 0)
    return {"frequency_cycles_per_nm": freq, "amplitude": amp, "phase_rad": phase,
            "period_nm": period, "uniform_x": uniform_x, "uniform_y": yy}


def cwt_spectrum(x, y, *, wavelet: str = "morl", min_scale: int = 1, max_scale: int = 64) -> dict:
    x, y = _clean_xy(x, y)
    if len(x) < 8:
        raise ValueError("At least eight points are required for wavelet analysis.")
    dx = float(np.median(np.diff(x)))
    uniform_x = np.arange(x[0], x[-1] + dx * 0.5, dx)
    yy = np.interp(uniform_x, x, y)
    scales = np.arange(max(1, int(min_scale)), max(int(min_scale) + 1, int(max_scale) + 1))
    coeffs, freqs = pywt.cwt(yy, scales, wavelet, sampling_period=dx)
    power = np.abs(coeffs) ** 2
    return {"x": uniform_x, "scales": scales, "frequencies": freqs, "coefficients": coeffs, "power": power}


def dwt_denoise(y, *, wavelet: str = "sym8", level: int | None = None, threshold_scale: float = 1.0) -> np.ndarray:
    y = np.asarray(y, dtype=float)
    coeffs = pywt.wavedec(y, wavelet, level=level, mode="symmetric")
    if len(coeffs) < 2:
        return y.copy()
    detail = coeffs[-1]
    sigma = np.median(np.abs(detail - np.median(detail))) / 0.6745 if len(detail) else 0.0
    threshold = float(threshold_scale) * sigma * np.sqrt(2 * np.log(max(len(y), 2)))
    out = [coeffs[0]] + [pywt.threshold(c, threshold, mode="soft") for c in coeffs[1:]]
    rec = pywt.waverec(out, wavelet, mode="symmetric")
    return rec[:len(y)]


def snv(matrix) -> np.ndarray:
    X = np.asarray(matrix, dtype=float)
    if X.ndim == 1:
        X = X[None, :]
    mean = np.nanmean(X, axis=1, keepdims=True)
    std = np.nanstd(X, axis=1, ddof=1, keepdims=True)
    std[std == 0] = 1.0
    return (X - mean) / std


def msc(matrix, reference=None) -> np.ndarray:
    X = np.asarray(matrix, dtype=float)
    if X.ndim == 1:
        X = X[None, :]
    ref = np.nanmean(X, axis=0) if reference is None else np.asarray(reference, dtype=float)
    corrected = np.empty_like(X)
    for i, row in enumerate(X):
        slope, intercept = np.polyfit(ref, row, 1)
        corrected[i] = (row - intercept) / slope if slope != 0 else row
    return corrected


def pca_spectra(matrix, n_components: int = 2) -> dict:
    X = np.asarray(matrix, dtype=float)
    if X.ndim != 2 or min(X.shape) < 2:
        raise ValueError("PCA requires at least two spectra and two variables.")
    n = max(1, min(int(n_components), min(X.shape)))
    model = PCA(n_components=n)
    scores = model.fit_transform(X)
    return {"scores": scores, "loadings": model.components_,
            "explained_variance_ratio": model.explained_variance_ratio_, "model": model}


def pls_regression(matrix, response, n_components: int = 2) -> dict:
    X = np.asarray(matrix, dtype=float)
    y = np.asarray(response, dtype=float).ravel()
    mask = np.isfinite(y) & np.all(np.isfinite(X), axis=1)
    X, y = X[mask], y[mask]
    if len(y) < 3:
        raise ValueError("PLS requires at least three valid samples.")
    n = max(1, min(int(n_components), X.shape[1], len(y) - 1))
    model = PLSRegression(n_components=n, scale=True)
    model.fit(X, y)
    pred = model.predict(X).ravel()
    return {"predicted": pred, "residuals": y - pred, "r_squared": float(r2_score(y, pred)),
            "rmse": float(np.sqrt(mean_squared_error(y, pred))), "x_weights": model.x_weights_,
            "x_loadings": model.x_loadings_, "model": model}


def integrate_manual_range(x, y, xmin: float, xmax: float) -> dict:
    x, y = _clean_xy(x, y)
    lo, hi = sorted((float(xmin), float(xmax)))
    if hi <= x[0] or lo >= x[-1]:
        raise ValueError("Integration interval does not overlap the spectrum.")
    lo, hi = max(lo, float(x[0])), min(hi, float(x[-1]))
    mask = (x > lo) & (x < hi)
    xx = np.r_[lo, x[mask], hi]
    yy = np.r_[np.interp(lo, x, y), y[mask], np.interp(hi, x, y)]
    return {"signed_area": float(trapezoid(yy, xx)), "absolute_area": float(trapezoid(np.abs(yy), xx)),
            "x": xx, "y": yy}
