from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class DerivativeQuality:
    order: int
    median_step_nm: float
    max_step_deviation_percent: float
    points_per_fwhm: float | None
    smoothing_window_points: int
    smoothing_window_nm: float
    window_to_fwhm_ratio: float | None
    effective_polyorder: int
    status: str
    warnings: list[str]


def absorbance_quality(absorbance, *, caution_threshold: float = 1.5, severe_threshold: float = 2.0) -> dict:
    """Return instrument-agnostic absorbance quality flags.

    The thresholds are deliberately presented as cautions rather than universal
    rejection limits.  Actual usable absorbance depends on instrument stray
    light, bandwidth, detector linearity, sample chemistry and validated method.
    """
    y = np.asarray(absorbance, dtype=float).reshape(-1)
    finite = y[np.isfinite(y)]
    if finite.size == 0:
        return {"max_absorbance": np.nan, "status": "invalid", "warnings": ["No finite absorbance values."]}
    if caution_threshold <= 0 or severe_threshold <= caution_threshold:
        raise ValueError("Absorbance thresholds must satisfy 0 < caution < severe.")

    maximum = float(np.max(finite))
    warnings: list[str] = []
    status = "acceptable"
    if maximum > severe_threshold:
        status = "severe_caution"
        warnings.append(
            f"Maximum absorbance is {maximum:.3g} AU (> {severe_threshold:g} AU). "
            "High absorbance can become strongly instrument-dependent because of stray light and detector limits; "
            "consider dilution and verify the validated linear range."
        )
    elif maximum > caution_threshold:
        status = "caution"
        warnings.append(
            f"Maximum absorbance is {maximum:.3g} AU (> {caution_threshold:g} AU). "
            "Check instrument linearity/stray-light performance and the validated Beer-Lambert range before quantitation."
        )
    if float(np.min(finite)) < -0.05:
        warnings.append(
            "Negative absorbance below -0.05 AU was detected. Review blank/reference correction, baseline treatment and cuvette matching."
        )
    return {
        "max_absorbance": maximum,
        "min_absorbance": float(np.min(finite)),
        "status": status,
        "warnings": warnings,
    }


def derivative_quality(
    x,
    *,
    order: int,
    smoothing_window_points: int,
    requested_polyorder: int,
    fwhm_nm: float | None = None,
) -> DerivativeQuality:
    """Diagnose numerical/spectroscopic risk for high-order derivatives.

    No universal scan-step or smoothing-window acceptance limit exists for all
    UV-Vis instruments.  This function therefore reports quantitative geometry
    (step size and window/FWHM relationship) and conservative warnings rather
    than silently altering the data.
    """
    x = np.asarray(x, dtype=float).reshape(-1)
    x = x[np.isfinite(x)]
    if x.size < 3:
        raise ValueError("At least three finite wavelength points are required.")
    x = np.unique(np.sort(x))
    if x.size < 3:
        raise ValueError("At least three unique wavelength points are required.")

    order = int(order)
    if order < 0 or order > 4:
        raise ValueError("Derivative order must be between 0 and 4.")
    dx = np.diff(x)
    median_step = float(np.median(dx))
    if median_step <= 0:
        raise ValueError("Wavelength grid must be strictly increasing.")
    max_dev = float(np.max(np.abs(dx - median_step)) / median_step * 100.0)

    # analysis.derivative intentionally uses one degree above derivative order
    # for high orders, giving a local polynomial enough flexibility for 3D/4D.
    effective_poly = max(int(requested_polyorder), order + 1) if order > 0 else int(requested_polyorder)
    window = int(smoothing_window_points)
    if window % 2 == 0:
        window += 1
    minimum_window = effective_poly + 2
    if minimum_window % 2 == 0:
        minimum_window += 1
    window = max(window, minimum_window)
    window_nm = float((window - 1) * median_step)

    points_per_fwhm = None
    window_ratio = None
    warnings: list[str] = []
    status = "acceptable"

    if max_dev > 2.0:
        warnings.append(
            f"Wavelength spacing is non-uniform (maximum deviation {max_dev:.2f}% from median step). "
            "Coordinate-aware numerical differentiation is preferable to assuming a fixed delta-lambda."
        )
    if order >= 3:
        status = "caution"
        warnings.append(
            f"{order}th-order derivative strongly amplifies high-frequency noise. "
            "Verify repeatability, raw-spectrum S/N and derivative stability against reasonable smoothing settings."
        )
    if order == 4 and median_step > 0.5:
        warnings.append(
            f"Median wavelength step is {median_step:.3g} nm. For a fourth derivative this may provide limited sampling of narrow bands; "
            "0.5 nm is a conservative diagnostic reference, not a universal acceptance criterion."
        )

    if fwhm_nm is not None and np.isfinite(fwhm_nm) and float(fwhm_nm) > 0:
        fwhm = float(fwhm_nm)
        points_per_fwhm = fwhm / median_step
        window_ratio = window_nm / fwhm
        if points_per_fwhm < 7 and order >= 2:
            warnings.append(
                f"Only {points_per_fwhm:.2f} wavelength points span the supplied FWHM. "
                "High-order derivatives may be under-sampled."
            )
        if window_ratio > 0.5:
            warnings.append(
                f"Savitzky-Golay window spans {window_ratio:.2f}× the supplied FWHM. "
                "This can attenuate or broaden spectral features; confirm by sensitivity analysis."
            )
        elif window_ratio < 0.05 and order >= 3:
            warnings.append(
                f"Savitzky-Golay window spans only {window_ratio:.3f}× the supplied FWHM. "
                "Noise suppression may be insufficient for a high-order derivative."
            )

    if warnings and status == "acceptable":
        status = "caution"
    return DerivativeQuality(
        order=order,
        median_step_nm=median_step,
        max_step_deviation_percent=max_dev,
        points_per_fwhm=points_per_fwhm,
        smoothing_window_points=window,
        smoothing_window_nm=window_nm,
        window_to_fwhm_ratio=window_ratio,
        effective_polyorder=effective_poly,
        status=status,
        warnings=warnings,
    )
