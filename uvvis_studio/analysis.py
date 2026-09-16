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
    y = np.asarray(y, dtype=float)
    w = _safe_window(len(y), window, polyorder)
    if not w:
        return y.copy()
    return savgol_filter(y, window_length=w, polyorder=polyorder)


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
    if order <= 0:
        return y.copy()
    if len(x) < 2:
        return y.copy()

    # Savitzky-Golay derivatives are mathematically appropriate only on a
    # uniformly spaced wavelength grid. For irregular grids use np.gradient,
    # which respects the actual x coordinates.
    if _is_uniform_grid(x):
        dx = float(np.median(np.diff(x)))
        w = _safe_window(len(y), window, polyorder)
        if w and order <= polyorder:
            return savgol_filter(y, window_length=w, polyorder=polyorder, deriv=order, delta=dx)

    out = y.copy()
    for _ in range(int(order)):
        out = np.gradient(out, x, edge_order=2 if len(x) >= 3 else 1)
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
    x = np.asarray(x, dtype=float)
    yy = np.asarray(y, dtype=float).copy()
    if len(x) != len(yy):
        raise ValueError("x and y must have the same length.")
    if smooth:
        yy = smooth_savgol(yy, window, polyorder)
    if baseline:
        yy = yy - baseline_als(yy, baseline_lambda, baseline_p)
    yy = normalize(x, yy, normalization)
    yy = derivative(x, yy, derivative_order, window, polyorder)
    return x, yy


def _interpolated_fwhm(x: np.ndarray, y: np.ndarray, peak_index: int) -> float | None:
    """Return FWHM in x-units, including irregular wavelength grids."""
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


def peak_table(
    x: np.ndarray,
    y: np.ndarray,
    prominence: float | None = None,
    distance: int | None = None,
):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(y) == 0:
        return []
    yrange = float(np.nanmax(y) - np.nanmin(y))
    prom = prominence if prominence is not None else max(yrange * 0.03, np.finfo(float).eps)
    peaks, props = find_peaks(y, prominence=prom, distance=distance)
    rows = []
    for i, idx in enumerate(peaks):
        fwhm = _interpolated_fwhm(x, y, int(idx))
        rows.append(
            {
                "wavelength_nm": float(x[idx]),
                "intensity": float(y[idx]),
                "prominence": float(props["prominences"][i]),
                "fwhm_nm": fwhm,
            }
        )
    return rows
