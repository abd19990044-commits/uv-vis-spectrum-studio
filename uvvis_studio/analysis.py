from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from scipy import sparse
from scipy.integrate import trapezoid
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks, peak_widths, savgol_filter
from scipy.sparse.linalg import spsolve


@dataclass
class SpectrumMetrics:
    lambda_max: float
    y_max: float
    lambda_min: float
    y_min: float
    area: float
    absolute_area: float
    centroid: float
    fwhm: float | None
    peak_count: int


def crop_xy(x: np.ndarray, y: np.ndarray, xmin: float | None, xmax: float | None) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    if xmin is not None:
        mask &= x >= xmin
    if xmax is not None:
        mask &= x <= xmax
    xx, yy = x[mask], y[mask]
    order = np.argsort(xx)
    return xx[order], yy[order]


def _safe_window(n: int, requested: int, polyorder: int) -> int:
    if n < 3:
        return 0
    w = max(int(requested), int(polyorder) + 2)
    if w % 2 == 0:
        w += 1
    if w > n:
        w = n if n % 2 else n - 1
    return w if w > polyorder else 0


def smooth_savgol(y: np.ndarray, window: int = 11, polyorder: int = 3) -> np.ndarray:
    y = np.asarray(y, dtype=float)
    w = _safe_window(len(y), window, polyorder)
    if not w:
        return y.copy()
    return savgol_filter(y, window_length=w, polyorder=polyorder)


def smooth_signal(y: np.ndarray, method: str = "None", window: int = 11, polyorder: int = 3, sigma: float = 2.0) -> np.ndarray:
    y = np.asarray(y, dtype=float)
    if method == "None":
        return y.copy()
    if method == "Savitzky-Golay":
        return smooth_savgol(y, window, polyorder)
    if method == "Moving average":
        w = max(1, int(window))
        if w % 2 == 0:
            w += 1
        if w <= 1:
            return y.copy()
        kernel = np.ones(w, dtype=float) / w
        pad = w // 2
        yp = np.pad(y, pad, mode="edge")
        return np.convolve(yp, kernel, mode="valid")
    if method == "Gaussian":
        return gaussian_filter1d(y, sigma=max(float(sigma), 0.01), mode="nearest")
    raise ValueError(f"Unsupported smoothing method: {method}")


def baseline_als(y: np.ndarray, lam: float = 1e6, p: float = 0.01, niter: int = 10) -> np.ndarray:
    y = np.asarray(y, dtype=float)
    n = len(y)
    if n < 3:
        return np.zeros_like(y)
    if lam <= 0:
        raise ValueError("ALS lambda must be > 0.")
    if not 0 < p < 1:
        raise ValueError("ALS p must be between 0 and 1.")
    D = sparse.diags([1, -2, 1], [0, 1, 2], shape=(n - 2, n), format="csc")
    w = np.ones(n)
    z = np.zeros_like(y)
    for _ in range(max(1, int(niter))):
        W = sparse.spdiags(w, 0, n, n)
        Z = W + lam * (D.T @ D)
        z = spsolve(Z, w * y)
        w = p * (y > z) + (1 - p) * (y < z)
    return np.asarray(z)


def baseline_linear_endpoints(x: np.ndarray, y: np.ndarray, edge_fraction: float = 0.05) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(x)
    if n < 2:
        return np.zeros_like(y)
    k = max(1, int(round(n * max(min(edge_fraction, 0.45), 0.01))))
    x1, y1 = float(np.mean(x[:k])), float(np.mean(y[:k]))
    x2, y2 = float(np.mean(x[-k:])), float(np.mean(y[-k:]))
    if x2 == x1:
        return np.full_like(y, (y1 + y2) / 2)
    slope = (y2 - y1) / (x2 - x1)
    return y1 + slope * (x - x1)


def baseline_polynomial_edges(x: np.ndarray, y: np.ndarray, order: int = 2, edge_fraction: float = 0.1) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(x)
    if n < order + 2:
        return baseline_linear_endpoints(x, y, edge_fraction)
    k = max(order + 1, int(round(n * max(min(edge_fraction, 0.45), 0.02))))
    idx = np.unique(np.r_[np.arange(min(k, n)), np.arange(max(0, n - k), n)])
    coeff = np.polyfit(x[idx], y[idx], deg=min(int(order), len(idx) - 1))
    return np.polyval(coeff, x)


def normalize(x: np.ndarray, y: np.ndarray, mode: str) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if mode == "None":
        return y.copy()
    if mode == "Max = 1":
        m = float(np.nanmax(np.abs(y))) if len(y) else 0.0
        return y / m if m else y.copy()
    if mode == "Min-Max 0–1":
        lo, hi = float(np.nanmin(y)), float(np.nanmax(y))
        return (y - lo) / (hi - lo) if hi != lo else y.copy()
    if mode == "Area = 1":
        a = float(trapezoid(np.abs(y), x)) if len(x) > 1 else 0.0
        return y / a if a else y.copy()
    raise ValueError(f"Unsupported normalization mode: {mode}")


def _is_uniform_grid(x: np.ndarray, rtol: float = 2e-3) -> bool:
    if len(x) < 4:
        return True
    dx = np.diff(x)
    med = float(np.median(dx))
    if med == 0:
        return False
    return bool(np.allclose(dx, med, rtol=rtol, atol=max(abs(med) * rtol, 1e-12)))


def derivative(x: np.ndarray, y: np.ndarray, order: int = 0, window: int = 11, polyorder: int = 3) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    order = int(order)
    if order <= 0:
        return y.copy()
    if order > 4:
        raise ValueError("Derivative order must be between 0 and 4.")
    if len(x) < 2:
        return y.copy()

    if _is_uniform_grid(x):
        dx = float(np.median(np.diff(x)))
        effective_poly = max(int(polyorder), order + 1)
        w = _safe_window(len(y), window, effective_poly)
        if w:
            return savgol_filter(y, window_length=w, polyorder=effective_poly, deriv=order, delta=dx)

    out = y.copy()
    for _ in range(order):
        out = np.gradient(out, x, edge_order=2 if len(x) >= 3 else 1)
    return out


def process_spectrum(
    x: np.ndarray,
    y: np.ndarray,
    *,
    smooth: bool = False,
    smoothing_method: str | None = None,
    window: int = 11,
    polyorder: int = 3,
    gaussian_sigma: float = 2.0,
    baseline: bool = False,
    baseline_method: str | None = None,
    baseline_lambda: float = 1e6,
    baseline_p: float = 0.01,
    baseline_poly_order: int = 2,
    baseline_edge_fraction: float = 0.1,
    normalization: str = "None",
    derivative_order: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(x, dtype=float)
    yy = np.asarray(y, dtype=float).copy()
    if len(x) != len(yy):
        raise ValueError("x and y must have the same length.")

    method = smoothing_method or ("Savitzky-Golay" if smooth else "None")
    yy = smooth_signal(yy, method, window, polyorder, gaussian_sigma)

    bmethod = baseline_method or ("ALS" if baseline else "None")
    if bmethod == "ALS":
        yy = yy - baseline_als(yy, baseline_lambda, baseline_p)
    elif bmethod == "Linear endpoints":
        yy = yy - baseline_linear_endpoints(x, yy, baseline_edge_fraction)
    elif bmethod == "Polynomial edges":
        yy = yy - baseline_polynomial_edges(x, yy, baseline_poly_order, baseline_edge_fraction)
    elif bmethod != "None":
        raise ValueError(f"Unsupported baseline method: {bmethod}")

    yy = normalize(x, yy, normalization)
    yy = derivative(x, yy, derivative_order, window, polyorder)
    return x, yy


def integrate_range(x: np.ndarray, y: np.ndarray, xmin: float, xmax: float) -> tuple[float, float, np.ndarray, np.ndarray]:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    lo, hi = sorted((float(xmin), float(xmax)))
    if len(x) < 2 or hi <= x[0] or lo >= x[-1]:
        return 0.0, 0.0, np.array([]), np.array([])
    lo = max(lo, float(x[0]))
    hi = min(hi, float(x[-1]))
    mask = (x > lo) & (x < hi)
    xx = np.r_[lo, x[mask], hi]
    yy = np.r_[np.interp(lo, x, y), y[mask], np.interp(hi, x, y)]
    return float(trapezoid(yy, xx)), float(trapezoid(np.abs(yy), xx)), xx, yy


def zero_crossings(x: np.ndarray, y: np.ndarray, tolerance: float = 0.0) -> list[dict[str, float]]:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    rows: list[dict[str, float]] = []
    if len(x) < 2:
        return rows
    tol = abs(float(tolerance))
    yy = y.copy()
    yy[np.abs(yy) <= tol] = 0.0
    for i in range(len(x) - 1):
        y1, y2 = yy[i], yy[i + 1]
        if y1 == 0:
            xc = float(x[i])
        elif y1 * y2 < 0:
            xc = float(x[i] - y1 * (x[i + 1] - x[i]) / (y2 - y1))
        else:
            continue
        if not rows or abs(rows[-1]["wavelength_nm"] - xc) > 1e-9:
            rows.append({"wavelength_nm": xc})
    return rows


def signal_at_wavelength(x: np.ndarray, y: np.ndarray, wavelength: float) -> float:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    w = float(wavelength)
    if len(x) == 0 or w < x[0] or w > x[-1]:
        return float("nan")
    return float(np.interp(w, x, y))


def estimate_snr(x: np.ndarray, y: np.ndarray, noise_min: float, noise_max: float) -> dict[str, float]:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    xn, yn = crop_xy(x, y, min(noise_min, noise_max), max(noise_min, noise_max))
    if len(yn) < 3:
        return {"noise_sd": float("nan"), "peak_signal": float("nan"), "snr": float("nan")}
    noise_sd = float(np.std(yn, ddof=1))
    baseline = float(np.mean(yn))
    peak_signal = float(np.nanmax(np.abs(y - baseline)))
    return {"noise_sd": noise_sd, "peak_signal": peak_signal, "snr": peak_signal / noise_sd if noise_sd > 0 else float("inf")}


def absorbance_to_transmittance(absorbance: np.ndarray) -> np.ndarray:
    return 100.0 * np.power(10.0, -np.asarray(absorbance, dtype=float))


def transmittance_to_absorbance(transmittance_percent: np.ndarray) -> np.ndarray:
    t = np.asarray(transmittance_percent, dtype=float)
    out = np.full_like(t, np.nan, dtype=float)
    valid = t > 0
    out[valid] = -np.log10(t[valid] / 100.0)
    return out


def spectral_arithmetic(x1: np.ndarray, y1: np.ndarray, x2: np.ndarray, y2: np.ndarray, operation: str) -> tuple[np.ndarray, np.ndarray]:
    x1 = np.asarray(x1, dtype=float)
    y1 = np.asarray(y1, dtype=float)
    x2 = np.asarray(x2, dtype=float)
    y2 = np.asarray(y2, dtype=float)
    lo = max(float(np.min(x1)), float(np.min(x2)))
    hi = min(float(np.max(x1)), float(np.max(x2)))
    mask = (x1 >= lo) & (x1 <= hi)
    x = x1[mask]
    a = y1[mask]
    b = np.interp(x, x2, y2)
    if operation in {"Subtract B from A", "Blank/reference subtraction", "Difference A − B"}:
        return x, a - b
    if operation == "Add A + B":
        return x, a + b
    if operation == "Ratio A / B":
        return x, np.divide(a, b, out=np.full_like(a, np.nan), where=np.abs(b) > np.finfo(float).eps)
    raise ValueError(f"Unsupported spectral arithmetic operation: {operation}")


def _interpolated_fwhm(x: np.ndarray, y: np.ndarray, peak_index: int) -> float | None:
    if len(x) < 3:
        return None
    results = peak_widths(y, [peak_index], rel_height=0.5)
    left_ip = float(results[2][0])
    right_ip = float(results[3][0])
    indices = np.arange(len(x), dtype=float)
    left_x = float(np.interp(left_ip, indices, x))
    right_x = float(np.interp(right_ip, indices, x))
    width = right_x - left_x
    return width if np.isfinite(width) and width >= 0 else None


def calculate_metrics(x: np.ndarray, y: np.ndarray, prominence: float | None = None) -> SpectrumMetrics:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    if len(x) == 0:
        raise ValueError("Spectrum is empty after cropping.")

    imax, imin = int(np.nanargmax(y)), int(np.nanargmin(y))
    signed_area = float(trapezoid(y, x)) if len(x) > 1 else 0.0
    absolute_area = float(trapezoid(np.abs(y), x)) if len(x) > 1 else 0.0
    centroid = float(trapezoid(x * np.abs(y), x) / absolute_area) if absolute_area else float("nan")

    if prominence is None:
        yrange = float(np.nanmax(y) - np.nanmin(y))
        prominence = max(yrange * 0.03, np.finfo(float).eps)
    peaks, _ = find_peaks(y, prominence=prominence)
    fwhm = None
    if len(peaks):
        main_peak = int(peaks[int(np.argmax(y[peaks]))])
        fwhm = _interpolated_fwhm(x, y, main_peak)

    return SpectrumMetrics(
        lambda_max=float(x[imax]),
        y_max=float(y[imax]),
        lambda_min=float(x[imin]),
        y_min=float(y[imin]),
        area=signed_area,
        absolute_area=absolute_area,
        centroid=centroid,
        fwhm=fwhm,
        peak_count=int(len(peaks)),
    )


def peak_table(x: np.ndarray, y: np.ndarray, prominence: float | None = None, distance: int | None = None):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(y) == 0:
        return []
    yrange = float(np.nanmax(y) - np.nanmin(y))
    prom = prominence if prominence is not None else max(yrange * 0.03, np.finfo(float).eps)
    peaks, props = find_peaks(y, prominence=prom, distance=distance)
    rows = []
    for i, idx in enumerate(peaks):
        rows.append({
            "wavelength_nm": float(x[idx]),
            "intensity": float(y[idx]),
            "prominence": float(props["prominences"][i]),
            "fwhm_nm": _interpolated_fwhm(x, y, int(idx)),
        })
    return rows
