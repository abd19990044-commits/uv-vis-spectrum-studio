from __future__ import annotations

import numpy as np
import pywt
from scipy.signal import detrend as scipy_detrend


def uniform_resample(x: np.ndarray, y: np.ndarray, points: int | None = None) -> tuple[np.ndarray, np.ndarray]:
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


def fft_analysis(x: np.ndarray, y: np.ndarray, *, detrend: bool = True, window: str = "Hann") -> dict:
    x, y = uniform_resample(x, y)
    if len(x) < 4:
        raise ValueError("At least four points are required for FFT analysis.")
    dx = float(np.median(np.diff(x)))
    yy = scipy_detrend(y, type="linear") if detrend else y - np.mean(y)
    win = np.ones(len(yy))
    if window == "Hann": win = np.hanning(len(yy))
    elif window == "Hamming": win = np.hamming(len(yy))
    elif window == "Blackman": win = np.blackman(len(yy))
    elif window != "None": raise ValueError(f"Unsupported FFT window: {window}")
    spec = np.fft.rfft(yy * win)
    freq = np.fft.rfftfreq(len(yy), d=dx)
    amplitude = np.abs(spec)
    power = amplitude**2
    period = np.full_like(freq, np.nan, dtype=float)
    valid = freq > 0
    period[valid] = 1.0 / freq[valid]
    dominant_period = float("nan")
    if np.count_nonzero(valid):
        idx = int(np.argmax(power[1:]) + 1)
        dominant_period = float(period[idx])
    return {"frequency_per_nm": freq, "amplitude": amplitude, "power": power, "period_nm": period, "dominant_period_nm": dominant_period, "dx_nm": dx}


def fft_lowpass(x: np.ndarray, y: np.ndarray, cutoff_fraction_nyquist: float = 0.15) -> tuple[np.ndarray, np.ndarray]:
    x, y = uniform_resample(x, y)
    if len(x) < 4: return x, y
    frac = float(cutoff_fraction_nyquist)
    if not 0 < frac <= 1: raise ValueError("FFT cutoff fraction must be in (0, 1].")
    dx = float(np.median(np.diff(x)))
    freq = np.fft.rfftfreq(len(y), d=dx)
    spec = np.fft.rfft(y)
    spec[freq > frac * float(np.max(freq))] = 0
    return x, np.fft.irfft(spec, n=len(y))


def wavelet_denoise(y: np.ndarray, *, wavelet: str = "db4", level: int | None = None, threshold_scale: float = 1.0, mode: str = "soft") -> np.ndarray:
    y = np.asarray(y, dtype=float)
    if len(y) < 4: return y.copy()
    wave = pywt.Wavelet(wavelet)
    max_level = pywt.dwt_max_level(len(y), wave.dec_len)
    use_level = max_level if level is None else min(max(int(level), 1), max_level)
    if use_level < 1: return y.copy()
    coeffs = pywt.wavedec(y, wave, level=use_level)
    detail = coeffs[-1]
    sigma = float(np.median(np.abs(detail - np.median(detail))) / 0.6745) if len(detail) else 0.0
    threshold = float(threshold_scale) * sigma * np.sqrt(2.0 * np.log(max(len(y), 2)))
    filtered = [coeffs[0]] + [pywt.threshold(c, threshold, mode=mode) for c in coeffs[1:]]
    return np.asarray(pywt.waverec(filtered, wave)[: len(y)], dtype=float)


def cwt_analysis(x: np.ndarray, y: np.ndarray, *, wavelet: str = "morl", min_scale: int = 1, max_scale: int = 64) -> dict:
    x, y = uniform_resample(x, y)
    if len(x) < 8: raise ValueError("At least eight points are required for CWT analysis.")
    lo, hi = sorted((max(1, int(min_scale)), max(2, int(max_scale))))
    scales = np.arange(lo, hi + 1)
    dx = float(np.median(np.diff(x)))
    coeff, frequencies = pywt.cwt(y - np.mean(y), scales, wavelet, sampling_period=dx)
    return {"x_nm": x, "scales": scales.astype(float), "coefficients": coeff, "power": np.abs(coeff) ** 2, "frequency_per_nm": np.asarray(frequencies, dtype=float)}
