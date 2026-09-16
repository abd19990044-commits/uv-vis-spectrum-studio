from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from scipy import sparse
from scipy.integrate import trapezoid
from scipy.signal import find_peaks, peak_widths, savgol_filter
from scipy.sparse.linalg import spsolve


@dataclass
class SpectrumMetrics:
    lambda_max: float
    y_max: float
    lambda_min: float
    y_min: float
    area: float
    centroid: float
    fwhm: float | None
    peak_count: int


def crop_xy(x: np.ndarray, y: np.ndarray, xmin: float | None, xmax: float | None) -> tuple[np.ndarray, np.ndarray]:
    mask = np.ones_like(x, dtype=bool)
    if xmin is not None:
        mask &= x >= xmin
    if xmax is not None:
        mask &= x <= xmax
    return x[mask], y[mask]


def _safe_window(n: int, requested: int, polyorder: int) -> int:
    if n < 3:
        return 0
    w = max(int(requested), polyorder + 2)
    if w % 2 == 0:
        w += 1
    if w > n:
        w = n if n % 2 else n - 1
    return w if w > polyorder else 0


def smooth_savgol(y: np.ndarray, window: int = 11, polyorder: int = 3) -> np.ndarray:
    w = _safe_window(len(y), window, polyorder)
    if not w:
        return y.copy()
    return savgol_filter(y, window_length=w, polyorder=polyorder)


def baseline_als(y: np.ndarray, lam: float = 1e6, p: float = 0.01, niter: int = 10) -> np.ndarray:
    n = len(y)
    if n < 3:
        return np.zeros_like(y)
    D = sparse.diags([1, -2, 1], [0, 1, 2], shape=(n - 2, n), format="csc")
    w = np.ones(n)
    for _ in range(niter):
        W = sparse.spdiags(w, 0, n, n)
        Z = W + lam * (D.T @ D)
        z = spsolve(Z, w * y)
        w = p * (y > z) + (1 - p) * (y < z)
    return np.asarray(z)


def normalize(y: np.ndarray, mode: str) -> np.ndarray:
    if mode == "None":
        return y
    if mode == "Max = 1":
        m = np.nanmax(np.abs(y))
        return y / m if m else y
    if mode == "Min-Max 0–1":
        lo, hi = np.nanmin(y), np.nanmax(y)
        return (y - lo) / (hi - lo) if hi != lo else y
    if mode == "Area = 1":
        a = np.trapezoid(np.abs(y))
        return y / a if a else y
    return y


def derivative(x: np.ndarray, y: np.ndarray, order: int = 0, window: int = 11, polyorder: int = 3) -> np.ndarray:
    if order <= 0:
        return y
    if len(x) < 3:
        return np.gradient(y, x) if len(x) > 1 else y
    dx = float(np.median(np.diff(x)))
    w = _safe_window(len(y), window, polyorder)
    if w and order <= polyorder:
        return savgol_filter(y, window_length=w, polyorder=polyorder, deriv=order, delta=dx)
    out = y.copy()
    for _ in range(order):
        out = np.gradient(out, x)
    return out


def process_spectrum(
    x: np.ndarray,
    y: np.ndarray,
    *,
    smooth: bool = False,
    window: int = 11,
    polyorder: int = 3,
    baseline: bool = False,
    baseline_lambda: float = 1e6,
    baseline_p: float = 0.01,
    normalization: str = "None",
    derivative_order: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    yy = y.astype(float).copy()
    if smooth:
        yy = smooth_savgol(yy, window, polyorder)
    if baseline:
        yy = yy - baseline_als(yy, baseline_lambda, baseline_p)
    yy = normalize(yy, normalization)
    yy = derivative(x, yy, derivative_order, window, polyorder)
    return x, yy


def calculate_metrics(x: np.ndarray, y: np.ndarray, prominence: float | None = None) -> SpectrumMetrics:
    if len(x) == 0:
        raise ValueError("Spectrum is empty after cropping.")
    imax, imin = int(np.nanargmax(y)), int(np.nanargmin(y))
    area = float(trapezoid(y, x)) if len(x) > 1 else 0.0
    denom = float(trapezoid(np.abs(y), x)) if len(x) > 1 else 0.0
    centroid = float(trapezoid(x * np.abs(y), x) / denom) if denom else float("nan")

    if prominence is None:
        yrange = float(np.nanmax(y) - np.nanmin(y))
        prominence = max(yrange * 0.03, np.finfo(float).eps)
    peaks, props = find_peaks(y, prominence=prominence)
    fwhm = None
    if len(peaks):
        main_peak = peaks[int(np.argmax(y[peaks]))]
        widths = peak_widths(y, [main_peak], rel_height=0.5)[0]
        if len(x) > 1:
            fwhm = float(widths[0] * np.median(np.diff(x)))
    return SpectrumMetrics(
        lambda_max=float(x[imax]), y_max=float(y[imax]),
        lambda_min=float(x[imin]), y_min=float(y[imin]),
        area=area, centroid=centroid, fwhm=fwhm, peak_count=int(len(peaks)),
    )


def peak_table(x: np.ndarray, y: np.ndarray, prominence: float | None = None, distance: int | None = None):
    yrange = float(np.nanmax(y) - np.nanmin(y)) if len(y) else 0.0
    prom = prominence if prominence is not None else max(yrange * 0.03, np.finfo(float).eps)
    peaks, props = find_peaks(y, prominence=prom, distance=distance)
    rows = []
    for i, idx in enumerate(peaks):
        rows.append({
            "wavelength_nm": float(x[idx]),
            "intensity": float(y[idx]),
            "prominence": float(props["prominences"][i]),
        })
    return rows
