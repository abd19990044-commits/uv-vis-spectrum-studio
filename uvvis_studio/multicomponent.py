from __future__ import annotations

import numpy as np


def _conditioning_status(condition_number: float, warn_threshold: float, hard_threshold: float) -> tuple[str, str | None]:
    if not np.isfinite(condition_number):
        return "singular", "Absorptivity matrix is singular or numerically non-finite."
    if condition_number >= hard_threshold:
        return "unreliable", (
            "Absorptivity matrix is extremely ill-conditioned; concentration results are not numerically reliable. "
            "Choose more selective wavelengths or use a validated multivariate method."
        )
    if condition_number >= warn_threshold:
        return "caution", (
            "Absorptivity matrix is ill-conditioned. Small absorbance or absorptivity errors may be strongly amplified. "
            "Inspect wavelength selectivity and uncertainty before reporting concentrations."
        )
    return "acceptable", None


def simultaneous_equations(
    a1,
    a2,
    eps_a1,
    eps_a2,
    eps_b1,
    eps_b2,
    path_length_cm=1.0,
    *,
    condition_warning: float = 1e4,
    condition_hard_limit: float = 1e12,
):
    """Solve a two-component Beer-Lambert system with conditioning diagnostics.

    Condition-number thresholds are numerical safeguards, not universal chemical
    acceptance criteria.  The reported condition number should always be
    interpreted alongside experimental uncertainty, wavelength selectivity and
    method validation.
    """
    l = float(path_length_cm)
    if not np.isfinite(l) or l <= 0:
        raise ValueError("Path length must be finite and positive.")
    if condition_warning <= 1 or condition_hard_limit <= condition_warning:
        raise ValueError("Condition-number thresholds must satisfy 1 < warning < hard limit.")

    matrix = np.array(
        [[float(eps_a1), float(eps_b1)], [float(eps_a2), float(eps_b2)]],
        dtype=float,
    ) * l
    response = np.array([float(a1), float(a2)], dtype=float)
    if not np.all(np.isfinite(matrix)) or not np.all(np.isfinite(response)):
        raise ValueError("Absorbance and absorptivity values must be finite.")

    condition_number = float(np.linalg.cond(matrix))
    status, warning = _conditioning_status(condition_number, condition_warning, condition_hard_limit)
    if status in {"singular", "unreliable"}:
        raise ValueError(f"{warning} condition_number={condition_number:.6g}")

    concentration = np.linalg.solve(matrix, response)
    return {
        "concentration_A": float(concentration[0]),
        "concentration_B": float(concentration[1]),
        "condition_number": condition_number,
        "conditioning_status": status,
        "conditioning_warning": warning,
        "matrix": matrix,
    }


def q_absorbance_ratio(
    a_iso,
    a_lambda,
    eps_a_iso,
    eps_a_lambda,
    eps_b_iso,
    eps_b_lambda,
    path_length_cm=1.0,
):
    a_iso = float(a_iso)
    a_lambda = float(a_lambda)
    l = float(path_length_cm)
    if not np.isfinite(a_iso) or not np.isfinite(a_lambda):
        raise ValueError("Absorbance values must be finite.")
    if a_iso == 0 or l <= 0:
        raise ValueError("Isoabsorptive absorbance and path length must be non-zero/positive.")
    qa = float(eps_a_lambda) / float(eps_a_iso)
    qb = float(eps_b_lambda) / float(eps_b_iso)
    qm = a_lambda / a_iso
    if abs(qa - qb) < 1e-15:
        raise ValueError("Q values for the two components are indistinguishable.")
    total = a_iso / (float(eps_a_iso) * l)
    frac_a = (qm - qb) / (qa - qb)
    ca = total * frac_a
    cb = total - ca
    warning = None
    if frac_a < 0 or frac_a > 1:
        warning = (
            "Calculated component fraction lies outside [0, 1]. Check absorptivities, wavelength selection, "
            "blank correction and whether the binary Beer-Lambert assumptions are satisfied."
        )
    return {
        "Qm": qm,
        "Qa": qa,
        "Qb": qb,
        "fraction_A": frac_a,
        "concentration_A": ca,
        "concentration_B": cb,
        "total_concentration": total,
        "warning": warning,
    }


def dual_wavelength(signal1_sample, signal2_sample, signal1_standard, signal2_standard, standard_concentration):
    ds = float(signal1_sample) - float(signal2_sample)
    dstd = float(signal1_standard) - float(signal2_standard)
    if abs(dstd) < 1e-15:
        raise ValueError("Standard differential response is zero.")
    return {
        "delta_sample": ds,
        "delta_standard": dstd,
        "concentration": float(standard_concentration) * ds / dstd,
    }


def ratio_spectrum(x, numerator, denominator, divisor_scale=1.0):
    x = np.asarray(x, dtype=float)
    n = np.asarray(numerator, dtype=float)
    d = np.asarray(denominator, dtype=float) * float(divisor_scale)
    if len(x) != len(n) or len(x) != len(d):
        raise ValueError("Ratio-spectrum arrays must have equal length.")
    out = np.full_like(n, np.nan, dtype=float)
    mask = np.isfinite(n) & np.isfinite(d) & (np.abs(d) > 1e-15)
    out[mask] = n[mask] / d[mask]
    return x, out


def mean_center_ratio(ratio):
    r = np.asarray(ratio, dtype=float)
    mask = np.isfinite(r)
    out = r.copy()
    if np.any(mask):
        out[mask] = r[mask] - np.mean(r[mask])
    return out


def derivative_ratio(x, ratio, order=1):
    x = np.asarray(x, dtype=float)
    y = np.asarray(ratio, dtype=float)
    if len(x) != len(y):
        raise ValueError("x and ratio must have equal length.")
    if int(order) < 1:
        return y.copy()
    if np.any(~np.isfinite(x)) or np.any(np.diff(x) <= 0):
        raise ValueError("x must be finite and strictly increasing for ratio-spectrum derivatives.")
    out = y.copy()
    for _ in range(int(order)):
        out = np.gradient(out, x, edge_order=2 if len(x) >= 3 else 1)
    return out
