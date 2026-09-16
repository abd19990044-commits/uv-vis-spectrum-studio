import numpy as np

from uvvis_studio.quantitation import isosbestic_points, linear_calibration


def test_linear_calibration_exact_line():
    c = np.array([0.0, 1.0, 2.0, 3.0])
    y = 2.5 * c + 0.2
    result = linear_calibration(c, y, sigma=0.05)
    assert abs(result.slope - 2.5) < 1e-12
    assert abs(result.intercept - 0.2) < 1e-12
    assert abs(result.r2 - 1.0) < 1e-12
    assert abs(result.lod - (3.3 * 0.05 / 2.5)) < 1e-12
    assert abs(result.loq - (10.0 * 0.05 / 2.5)) < 1e-12


def test_isosbestic_interpolation():
    x = np.linspace(200.0, 400.0, 201)
    y1 = x - 300.25
    y2 = -(x - 300.25)
    pts = isosbestic_points(x, y1, x, y2)
    assert pts
    assert abs(pts[0]["wavelength_nm"] - 300.25) < 1e-9
    assert abs(pts[0]["signal"]) < 1e-9
