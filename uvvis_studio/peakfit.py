from __future__ import annotations

import numpy as np
from scipy.optimize import curve_fit
from scipy.special import wofz


def gaussian(x, amp, center, sigma):
    sigma = max(abs(float(sigma)), 1e-12)
    return float(amp) * np.exp(-0.5 * ((x - float(center)) / sigma) ** 2)


def lorentzian(x, amp, center, gamma):
    gamma = max(abs(float(gamma)), 1e-12)
    return float(amp) * (gamma**2) / ((x - float(center)) ** 2 + gamma**2)


def voigt(x, amp, center, sigma, gamma):
    sigma = max(abs(float(sigma)), 1e-12)
    gamma = max(abs(float(gamma)), 1e-12)
    z = ((x - float(center)) + 1j * gamma) / (sigma * np.sqrt(2))
    profile = np.real(wofz(z)) / (sigma * np.sqrt(2 * np.pi))
    maximum = np.max(profile)
    return float(amp) * profile / maximum if maximum > 0 else np.zeros_like(x, dtype=float)


def pseudo_voigt(x, amp, center, fwhm, eta):
    """Peak-height-normalized pseudo-Voigt with a *common FWHM*.

    Both Gaussian and Lorentzian basis functions are parameterized so that the
    supplied ``fwhm`` is the full width at half maximum of each basis.  The
    mixture therefore also has half-height at center ± FWHM/2.  This avoids the
    common but incorrect practice of using one width as Gaussian sigma and
    Lorentzian HWHM simultaneously.
    """
    width = max(abs(float(fwhm)), 1e-12)
    eta = float(np.clip(eta, 0.0, 1.0))
    dx = (np.asarray(x, dtype=float) - float(center)) / width
    gaussian_part = np.exp(-4.0 * np.log(2.0) * dx**2)
    lorentzian_part = 1.0 / (1.0 + 4.0 * dx**2)
    return float(amp) * (eta * lorentzian_part + (1.0 - eta) * gaussian_part)


def _component(x, kind, params):
    if kind == "Gaussian":
        return gaussian(x, *params)
    if kind == "Lorentzian":
        return lorentzian(x, *params)
    if kind == "Voigt":
        return voigt(x, *params)
    if kind == "Pseudo-Voigt":
        return pseudo_voigt(x, *params)
    raise ValueError(f"Unsupported peak shape: {kind}")


def fit_peaks(x, y, centers, kind="Gaussian", baseline_order=1):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    order = np.argsort(x)
    x, y = x[order], y[order]
    centers = [float(center) for center in centers]
    if len(x) < 8 or not centers:
        raise ValueError("Peak fitting requires spectral data and at least one initial peak center.")
    if np.any(np.diff(x) <= 0):
        raise ValueError("Peak fitting requires strictly increasing unique X values.")
    if kind not in {"Gaussian", "Lorentzian", "Voigt", "Pseudo-Voigt"}:
        raise ValueError(f"Unsupported peak shape: {kind}")

    span = max(float(np.ptp(x)), 1e-6)
    amplitude_span = max(float(np.ptp(y)), 1e-6)
    initial_scale = max(
        span / (12 * max(len(centers), 1)),
        float(np.median(np.diff(x))) * 2,
    )

    p0: list[float] = []
    lower: list[float] = []
    upper: list[float] = []
    for center in centers:
        local = float(np.interp(center, x, y) - np.nanmin(y))
        amplitude = max(local, amplitude_span / 5)
        if kind in {"Gaussian", "Lorentzian"}:
            p0 += [amplitude, center, initial_scale]
            lower += [0.0, float(x.min()), 1e-9]
            upper += [np.inf, float(x.max()), span]
        elif kind == "Voigt":
            p0 += [amplitude, center, initial_scale, initial_scale]
            lower += [0.0, float(x.min()), 1e-9, 1e-9]
            upper += [np.inf, float(x.max()), span, span]
        else:
            # Pseudo-Voigt parameter 3 is common FWHM, parameter 4 is eta.
            p0 += [amplitude, center, 2.354820045 * initial_scale, 0.5]
            lower += [0.0, float(x.min()), 1e-9, 0.0]
            upper += [np.inf, float(x.max()), span, 1.0]

    baseline_order = max(0, min(int(baseline_order), 3))
    coefficients = np.polyfit(x, y, baseline_order)
    p0 += list(coefficients)
    lower += [-np.inf] * (baseline_order + 1)
    upper += [np.inf] * (baseline_order + 1)

    n_params = {"Gaussian": 3, "Lorentzian": 3, "Voigt": 4, "Pseudo-Voigt": 4}[kind]

    def model(xx, *parameters):
        output = np.zeros_like(xx, dtype=float)
        offset = 0
        for _ in centers:
            output += _component(xx, kind, parameters[offset : offset + n_params])
            offset += n_params
        return output + np.polyval(parameters[offset:], xx)

    popt, covariance = curve_fit(
        model,
        x,
        y,
        p0=p0,
        bounds=(lower, upper),
        maxfev=100000,
    )
    fit = model(x, *popt)
    residual = y - fit
    ss_res = float(np.sum(residual**2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0

    covariance_condition = float(np.linalg.cond(covariance)) if np.all(np.isfinite(covariance)) else np.inf
    with np.errstate(invalid="ignore"):
        standard_errors = np.sqrt(np.diag(covariance))
    standard_errors = np.asarray(standard_errors, dtype=float)

    components = []
    offset = 0
    for index in range(len(centers)):
        parameters = popt[offset : offset + n_params]
        errors = standard_errors[offset : offset + n_params]
        curve = _component(x, kind, parameters)
        area = float(np.trapezoid(curve, x))
        center = float(parameters[1])
        if kind == "Gaussian":
            fwhm = 2.354820045 * abs(float(parameters[2]))
        elif kind == "Lorentzian":
            fwhm = 2.0 * abs(float(parameters[2]))
        elif kind == "Pseudo-Voigt":
            fwhm = abs(float(parameters[2]))
        else:
            sigma = abs(float(parameters[2]))
            gamma = abs(float(parameters[3]))
            gaussian_fwhm = 2.354820045 * sigma
            lorentzian_fwhm = 2.0 * gamma
            fwhm = 0.5346 * lorentzian_fwhm + np.sqrt(
                0.2166 * lorentzian_fwhm**2 + gaussian_fwhm**2
            )
        components.append(
            {
                "peak": index + 1,
                "center": center,
                "amplitude": float(parameters[0]),
                "fwhm": float(fwhm),
                "area": area,
                "curve": curve,
                "parameters": np.asarray(parameters),
                "parameter_standard_errors": np.asarray(errors),
            }
        )
        offset += n_params

    warnings: list[str] = []
    if not np.all(np.isfinite(covariance)):
        warnings.append("Parameter covariance is non-finite; uncertainty estimates are unreliable.")
    elif covariance_condition > 1e12:
        warnings.append(
            "Peak-fit covariance is extremely ill-conditioned. Peak parameters may be highly correlated or non-identifiable; "
            "reduce model complexity, improve starting values, or acquire more selective data."
        )
    elif covariance_condition > 1e8:
        warnings.append(
            "Peak-fit covariance is ill-conditioned; interpret individual peak parameters and areas cautiously."
        )

    return {
        "x": x,
        "y": y,
        "fit": fit,
        "residual": residual,
        "components": components,
        "baseline": np.polyval(popt[offset:], x),
        "r2": float(r2),
        "rmse": float(np.sqrt(np.mean(residual**2))),
        "covariance": covariance,
        "covariance_condition_number": covariance_condition,
        "parameter_standard_errors": standard_errors,
        "parameters": popt,
        "warnings": warnings,
    }
