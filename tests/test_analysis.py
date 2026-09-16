import numpy as np
from scipy.integrate import trapezoid

from uvvis_studio.analysis import (
    calculate_metrics,
    crop_xy,
    derivative,
    integrate_range,
    normalize,
    spectral_arithmetic,
    zero_crossings,
)


def test_auc_and_lambda_max():
    x = np.linspace(200, 300, 101)
    y = np.ones_like(x) * 2
    m = calculate_metrics(x, y)
    assert abs(m.area - 200.0) < 1e-9
    assert abs(m.absolute_area - 200.0) < 1e-9
    assert m.lambda_max == 200.0


def test_first_derivative_linear_signal():
    x = np.linspace(200, 300, 101)
    y = 3 * x + 2
    dy = derivative(x, y, order=1, window=11, polyorder=3)
    assert np.allclose(dy[5:-5], 3.0, atol=1e-8)


def test_third_derivative_cubic_signal():
    x = np.linspace(-5, 5, 401)
    y = 2 * x**3 - 4 * x**2 + x + 8
    d3 = derivative(x, y, order=3, window=21, polyorder=5)
    assert np.allclose(d3[20:-20], 12.0, atol=1e-5)


def test_fourth_derivative_quartic_signal():
    x = np.linspace(-5, 5, 401)
    y = 3 * x**4 - 2 * x**3 + 5 * x**2 + 9
    d4 = derivative(x, y, order=4, window=25, polyorder=6)
    assert np.allclose(d4[25:-25], 72.0, atol=2e-4)


def test_first_derivative_irregular_grid():
    x = np.array([200.0, 201.0, 203.0, 206.0, 210.0, 215.0])
    y = 2.5 * x - 4.0
    dy = derivative(x, y, order=1)
    assert np.allclose(dy, 2.5, atol=1e-10)


def test_area_normalization_uses_wavelength_spacing():
    x = np.array([200.0, 201.0, 205.0, 212.0])
    y = np.array([1.0, 2.0, 2.0, 1.0])
    yn = normalize(x, y, "Area = 1")
    assert abs(trapezoid(np.abs(yn), x) - 1.0) < 1e-12


def test_integrate_range_interpolates_boundaries():
    x = np.array([0.0, 1.0, 2.0, 3.0])
    y = x.copy()
    signed, absolute, xx, yy = integrate_range(x, y, 0.5, 2.5)
    assert np.isclose(signed, 3.0)
    assert np.isclose(absolute, 3.0)
    assert np.isclose(xx[0], 0.5) and np.isclose(xx[-1], 2.5)
    assert np.isclose(yy[0], 0.5) and np.isclose(yy[-1], 2.5)


def test_zero_crossing_linear_interpolation():
    x = np.array([200.0, 210.0, 220.0])
    y = np.array([-1.0, 1.0, 2.0])
    z = zero_crossings(x, y)
    assert len(z) == 1
    assert np.isclose(z[0]["wavelength_nm"], 205.0)


def test_spectral_subtraction_interpolates_reference():
    x1 = np.array([200.0, 210.0, 220.0])
    y1 = np.array([3.0, 4.0, 5.0])
    x2 = np.array([200.0, 220.0])
    y2 = np.array([1.0, 3.0])
    x, y = spectral_arithmetic(x1, y1, x2, y2, "Blank/reference subtraction")
    assert np.allclose(x, x1)
    assert np.allclose(y, [2.0, 2.0, 2.0])


def test_crop():
    x = np.array([200, 250, 300], dtype=float)
    y = np.array([1, 2, 3], dtype=float)
    xx, yy = crop_xy(x, y, 225, 275)
    assert xx.tolist() == [250.0]
    assert yy.tolist() == [2.0]
