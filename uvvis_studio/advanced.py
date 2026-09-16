from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass
class CalibrationResult:
    slope: float
    intercept: float
    r_squared: float
    rmse: float
    n: int
    lod: float | None
    loq: float | None
    predicted: np.ndarray
    residuals: np.ndarray


def linear_calibration(concentration, signal, sigma: float | None = None) -> CalibrationResult:
    x = np.asarray(concentration, dtype=float)
    y = np.asarray(signal, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    if len(x) < 2:
        raise ValueError("At least two calibration points are required.")
    if np.ptp(x) == 0:
        raise ValueError("Calibration concentrations must not all be identical.")

    slope, intercept = np.polyfit(x, y, 1)
    predicted = slope * x + intercept
    residuals = y - predicted
    ss_res = float(np.sum(residuals**2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0
    rmse = float(np.sqrt(np.mean(residuals**2)))

    lod = loq = None
    if sigma is not None and np.isfinite(sigma) and sigma >= 0 and slope != 0:
        lod = float(3.3 * sigma / abs(slope))
        loq = float(10.0 * sigma / abs(slope))

    return CalibrationResult(
        slope=float(slope),
        intercept=float(intercept),
        r_squared=float(r_squared),
        rmse=rmse,
        n=int(len(x)),
        lod=lod,
        loq=loq,
        predicted=predicted,
        residuals=residuals,
    )


def isosbestic_points(x1, y1, x2, y2, tolerance: float | None = None) -> list[dict[str, float]]:
    x1 = np.asarray(x1, dtype=float)
    y1 = np.asarray(y1, dtype=float)
    x2 = np.asarray(x2, dtype=float)
    y2 = np.asarray(y2, dtype=float)

    m1 = np.isfinite(x1) & np.isfinite(y1)
    m2 = np.isfinite(x2) & np.isfinite(y2)
    x1, y1 = x1[m1], y1[m1]
    x2, y2 = x2[m2], y2[m2]
    if len(x1) < 2 or len(x2) < 2:
        return []

    o1 = np.argsort(x1)
    o2 = np.argsort(x2)
    x1, y1 = x1[o1], y1[o1]
    x2, y2 = x2[o2], y2[o2]
    lo = max(float(x1[0]), float(x2[0]))
    hi = min(float(x1[-1]), float(x2[-1]))
    if hi <= lo:
        return []

    mask = (x1 >= lo) & (x1 <= hi)
    x = x1[mask]
    if len(x) < 2:
        return []
    a = y1[mask]
    b = np.interp(x, x2, y2)
    d = a - b
    scale = max(float(np.nanmax(np.abs(np.r_[a, b]))), 1.0)
    tol = float(tolerance) if tolerance is not None else scale * 1e-8

    rows: list[dict[str, float]] = []
    for i in range(len(x) - 1):
        d1, d2 = float(d[i]), float(d[i + 1])
        if abs(d1) <= tol:
            xc = float(x[i])
        elif d1 * d2 < 0:
            xc = float(x[i] - d1 * (x[i + 1] - x[i]) / (d2 - d1))
        else:
            continue
        yc = float(np.interp(xc, x, (a + b) / 2.0))
        if not rows or abs(rows[-1]["wavelength_nm"] - xc) > 1e-7:
            rows.append({"wavelength_nm": xc, "signal": yc})
    return rows
