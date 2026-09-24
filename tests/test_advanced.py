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
def test_pls_component_limit_uses_smallest_cv_training_fold():
    import numpy as np
    from uvvis_studio.chemometrics_advanced import (
        interval_pls, nested_pls_evaluation, optimize_pls_components,
    )

    rng = np.random.default_rng(81)
    X = rng.normal(size=(8, 20))
    y = X[:, 0] * 0.5 + rng.normal(scale=0.01, size=8)
    wavelengths = np.linspace(200, 300, 20)
    exploratory = optimize_pls_components(X, y, max_components=15, cv_folds=5)
    assert max(row["components"] for row in exploratory["results"]) <= 6
    nested = nested_pls_evaluation(X, y, max_components=15, outer_folds=3, inner_folds=3)
    assert np.isfinite(nested["rmsep_nested"])
    assert len(nested["predicted"]) == len(y)
    intervals = interval_pls(X, y, wavelengths, n_intervals=2, n_components=15, cv_folds=5)
    assert len(intervals["results"]) == 2
