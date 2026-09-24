from __future__ import annotations

import numpy as np
import pywt
from scipy.signal import detrend as scipy_detrend


def check_grid_uniformity(x: np.ndarray, rtol: float = 2e-3) -> dict:
    """Assess whether a wavelength grid is uniformly sampled and return diagnostics."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 4:
        return {
            "is_uniform": True,
            "median_dx": float(np.median(np.diff(x))) if len(x) > 1 else 0.0,
            "min_dx": float(np.min(np.diff(x))) if len(x) > 1 else 0.0,
            "max_dx": float(np.max(np.diff(x))) if len(x) > 1 else 0.0,
            "std_dx": 0.0,
            "relative_spread": 0.0,
            "n_points": len(x),
            "range_nm": float(x[-1] - x[0]) if len(x) > 1 else 0.0,
        }
    dx = np.diff(x)
    med = float(np.median(dx))
    min_d = float(np.min(dx))
    max_d = float(np.max(dx))
    std_d = float(np.std(dx, ddof=1))
    spread = abs(max_d - min_d) / abs(med) if med != 0 else float("inf")
    is_uni = bool(np.allclose(dx, med, rtol=rtol, atol=max(abs(med) * rtol, 1e-12)))
    return {
        "is_uniform": is_uni,
        "median_dx": med,
        "min_dx": min_d,
        "max_dx": max_d,
        "std_dx": std_d,
        "relative_spread": spread,
        "n_points": len(x),
        "range_nm": float(np.max(x) - np.min(x)),
    }


def uniform_resample(x: np.ndarray, y: np.ndarray, points: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Resample spectrum onto a strictly uniform grid across the common range."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    order = np.argsort(x)
    x, y = x[order], y[order]
    if len(x) < 2:
        return x, y
    ux, idx = np.unique(x, return_index=True)
    y = y[idx]
    x = ux
    n = max(2, int(points or len(x)))
    xu = np.linspace(float(x[0]), float(x[-1]), n)
    return xu, np.interp(xu, x, y)


def fft_analysis(
    x: np.ndarray,
    y: np.ndarray,
    *,
    detrend: bool = True,
    window: str = "Hann",
    resample_if_nonuniform: bool = True,
) -> dict:
    """Perform Fourier analysis on a spectrum, computing spatial frequency (cycles/nm) and period (nm)."""
    grid_diag = check_grid_uniformity(x)
    resampled = False
    if not grid_diag["is_uniform"]:
        if not resample_if_nonuniform:
            raise ValueError(
                f"Nonuniform wavelength grid detected (relative spread: {grid_diag['relative_spread']:.2%}). "
                "FFT requires uniform sampling; please enable resampling or supply an evenly spaced grid."
            )
        x, y = uniform_resample(x, y)
        resampled = True
    else:
        # Sort coordinates if descending
        if np.any(np.diff(x) < 0):
            order = np.argsort(x)
            x, y = x[order], y[order]

    if len(x) < 4:
        raise ValueError("At least four points are required for FFT analysis.")

    n = len(y)
    dx = float(np.median(np.diff(x)))
    dc_component = float(np.mean(y))
    yy = scipy_detrend(y, type="linear") if detrend else y - dc_component

    # Windowing
    wname = str(window).strip().capitalize()
    if wname in {"None", "Rectangular"}:
        win = np.ones(n)
    elif wname == "Hann":
        win = np.hanning(n)
    elif wname == "Hamming":
        win = np.hamming(n)
    elif wname == "Blackman":
        win = np.blackman(n)
    elif wname == "Bartlett":
        win = np.bartlett(n)
    else:
        raise ValueError(f"Unsupported FFT window: {window}")

    win_coherent_gain = float(np.mean(win)) if np.mean(win) > 0 else 1.0
    spec = np.fft.rfft(yy * win)
    freq = np.fft.rfftfreq(n, d=dx)  # cycles per nm

    # Calibrated single-sided amplitude: 2 * |spec| / (N * coherent_gain)
    raw_amp = np.abs(spec)
    amplitude = (2.0 * raw_amp) / (n * win_coherent_gain)
    if len(amplitude) > 0:
        amplitude[0] = raw_amp[0] / (n * win_coherent_gain)  # DC term does not get factor of 2

    power = amplitude**2
    period = np.full_like(freq, np.nan, dtype=float)
    valid = freq > 0
    period[valid] = 1.0 / freq[valid]  # nm per cycle

    dominant_period = float("nan")
    dominant_freq = float("nan")
    if np.count_nonzero(valid):
        idx = int(np.argmax(power[1:]) + 1)
        dominant_period = float(period[idx])
        dominant_freq = float(freq[idx])

    return {
        "frequency_per_nm": freq,
        "amplitude": amplitude,
        "raw_amplitude": raw_amp,
        "power": power,
        "period_nm": period,
        "dominant_period_nm": dominant_period,
        "dominant_frequency_per_nm": dominant_freq,
        "dc_component": dc_component,
        "nyquist_frequency_per_nm": 1.0 / (2.0 * dx) if dx > 0 else float("nan"),
        "dx_nm": dx,
        "grid_uniform": grid_diag["is_uniform"],
        "was_resampled": resampled,
        "grid_diagnostics": grid_diag,
    }


def fft_lowpass(x: np.ndarray, y: np.ndarray, cutoff_fraction_nyquist: float = 0.15) -> tuple[np.ndarray, np.ndarray]:
    """Lowpass filter a spectrum via frequency-domain truncation."""
    x, y = uniform_resample(x, y)
    if len(x) < 4:
        return x, y
    frac = float(cutoff_fraction_nyquist)
    if not 0 < frac <= 1:
        raise ValueError("FFT cutoff fraction must be in (0, 1].")
    dx = float(np.median(np.diff(x)))
    freq = np.fft.rfftfreq(len(y), d=dx)
    spec = np.fft.rfft(y)
    spec[freq > frac * float(np.max(freq))] = 0
    return x, np.fft.irfft(spec, n=len(y))


def _compute_wavelet_threshold(
    detail_coeffs: np.ndarray,
    n_samples: int,
    rule: str = "VisuShrink",
    scale_factor: float = 1.0,
) -> tuple[float, float]:
    """Calculate wavelet denoising threshold and robust noise standard deviation (MAD/0.6745)."""
    if len(detail_coeffs) == 0:
        return 0.0, 0.0
    sigma = float(np.median(np.abs(detail_coeffs - np.median(detail_coeffs))) / 0.6745)
    r = str(rule).strip().lower()
    if r in {"visushrink", "universal"}:
        th = sigma * np.sqrt(2.0 * np.log(max(n_samples, 2)))
    elif r == "minimax":
        if n_samples <= 32:
            th = 0.0
        else:
            th = sigma * (0.3936 + 0.1829 * (np.log2(n_samples) / np.log2(1024.0)))
    elif r == "sure":
        # Stein's Unbiased Risk Estimate
        d = detail_coeffs / (sigma if sigma > 0 else 1.0)
        n = len(d)
        sorted_sq = np.sort(d**2)
        cumsum = np.cumsum(sorted_sq)
        risks = [(n - 2 * (i + 1) + cumsum[i] + (n - 1 - i) * sorted_sq[i]) for i in range(n)]
        best_i = int(np.argmin(risks))
        th = sigma * np.sqrt(max(sorted_sq[best_i], 0.0))
    else:
        # Default fallback to universal
        th = sigma * np.sqrt(2.0 * np.log(max(n_samples, 2)))
    return float(th * float(scale_factor)), float(sigma)


def wavelet_denoise_full(
    y: np.ndarray,
    *,
    wavelet: str = "db4",
    level: int | None = None,
    threshold_scale: float = 1.0,
    threshold_rule: str = "VisuShrink",
    mode: str = "soft",
) -> dict:
    """Comprehensive wavelet denoising returning reconstructed signal, residuals, and diagnostic statistics."""
    y = np.asarray(y, dtype=float)
    if len(y) < 4:
        return {
            "denoised": y.copy(),
            "residuals": np.zeros_like(y),
            "threshold": 0.0,
            "sigma": 0.0,
            "level": 0,
            "wavelet": wavelet,
        }
    wave = pywt.Wavelet(wavelet)
    max_level = pywt.dwt_max_level(len(y), wave.dec_len)
    use_level = max_level if level is None else min(max(int(level), 1), max_level)
    if use_level < 1:
        return {
            "denoised": y.copy(),
            "residuals": np.zeros_like(y),
            "threshold": 0.0,
            "sigma": 0.0,
            "level": 0,
            "wavelet": wavelet,
        }
    coeffs = pywt.wavedec(y, wave, level=use_level)
    detail = coeffs[-1]
    th, sigma = _compute_wavelet_threshold(detail, len(y), rule=threshold_rule, scale_factor=threshold_scale)
    filtered = [coeffs[0]] + [pywt.threshold(c, th, mode=mode) for c in coeffs[1:]]
    denoised = np.asarray(pywt.waverec(filtered, wave)[: len(y)], dtype=float)
    return {
        "denoised": denoised,
        "residuals": y - denoised,
        "threshold": th,
        "sigma": sigma,
        "level": use_level,
        "wavelet": wavelet,
        "mode": mode,
        "rule": threshold_rule,
    }


def wavelet_denoise(
    y: np.ndarray,
    *,
    wavelet: str = "db4",
    level: int | None = None,
    threshold_scale: float = 1.0,
    threshold_rule: str = "VisuShrink",
    mode: str = "soft",
) -> np.ndarray:
    """Discrete Wavelet Transform denoising returning filtered signal array."""
    res = wavelet_denoise_full(
        y,
        wavelet=wavelet,
        level=level,
        threshold_scale=threshold_scale,
        threshold_rule=threshold_rule,
        mode=mode,
    )
    return res["denoised"]


def cwt_analysis(
    x: np.ndarray,
    y: np.ndarray,
    *,
    wavelet: str = "morl",
    min_scale: int = 1,
    max_scale: int = 64,
) -> dict:
    """Continuous Wavelet Transform (CWT) scalogram analysis with edge-effect cone of influence diagnostics."""
    x, y = uniform_resample(x, y)
    if len(x) < 8:
        raise ValueError("At least eight points are required for CWT analysis.")
    lo, hi = sorted((max(1, int(min_scale)), max(2, int(max_scale))))
    scales = np.arange(lo, hi + 1)
    dx = float(np.median(np.diff(x)))
    centered_y = y - np.mean(y)
    coeff, frequencies = pywt.cwt(centered_y, scales, wavelet, sampling_period=dx)

    # Cone of influence (COI) diagnostic in nm: distance from edges where wavelet intersects boundary
    # For Morlet / standard wavelets, boundary e-folding zone is approx sqrt(2) * scale * dx
    coi_nm = np.sqrt(2.0) * scales.astype(float) * dx

    return {
        "x_nm": x,
        "scales": scales.astype(float),
        "coefficients": coeff,
        "power": np.abs(coeff) ** 2,
        "frequency_per_nm": np.asarray(frequencies, dtype=float),
        "pseudo_period_nm": 1.0 / np.asarray(frequencies, dtype=float),
        "cone_of_influence_nm": coi_nm,
        "dx_nm": dx,
        "wavelet": wavelet,
    }
