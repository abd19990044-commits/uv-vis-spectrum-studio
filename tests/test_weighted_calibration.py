import numpy as np

from uvvis_studio.quantitation import (
    breusch_pagan_calibration_test,
    weighted_linear_calibration,
)


def test_weighted_linear_calibration_recovers_exact_line():
    x = np.array([1.0, 2.0, 4.0, 8.0, 16.0])
    y = 0.25 + 1.75 * x
    result = weighted_linear_calibration(x, y, weighting="1/x")
    assert np.isclose(result.slope, 1.75, atol=1e-12)
    assert np.isclose(result.intercept, 0.25, atol=1e-12)
    assert np.allclose(result.predicted, y, atol=1e-12)
    assert result.weighted_r2 > 0.999999999999


def test_weighted_calibration_rejects_zero_for_reciprocal_x():
    x = np.array([0.0, 1.0, 2.0, 3.0])
    y = 0.1 + 2.0 * x
    try:
        weighted_linear_calibration(x, y, weighting="1/x")
    except ValueError as exc:
        assert "strictly positive" in str(exc)
    else:
        raise AssertionError("1/x weighting must reject a zero-concentration standard")


def test_custom_weighting_matches_manual_wls_solution():
    x = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    y = np.array([0.1, 1.05, 2.2, 2.9, 4.3])
    custom = np.array([4.0, 3.0, 2.0, 1.0, 0.5])
    result = weighted_linear_calibration(x, y, weighting="custom", custom_weights=custom)

    w = custom / custom.mean()
    X = np.column_stack([np.ones(len(x)), x])
    expected = np.linalg.solve(X.T @ (w[:, None] * X), X.T @ (w * y))
    assert np.allclose([result.intercept, result.slope], expected, rtol=1e-12, atol=1e-12)


def test_breusch_pagan_flags_strong_concentration_dependent_variance():
    rng = np.random.default_rng(20260917)
    x = np.repeat(np.linspace(1.0, 20.0, 10), 12)
    noise = rng.normal(0.0, 0.015 * x)
    y = 0.2 + 0.8 * x + noise
    result = breusch_pagan_calibration_test(x, y)
    assert result["p_value"] < 0.05
    assert result["heteroscedastic_at_0_05"] is True


def test_breusch_pagan_does_not_force_weighting_decision():
    x = np.linspace(1.0, 12.0, 24)
    deterministic_noise = 0.02 * np.sin(np.arange(x.size))
    y = 0.4 + 1.2 * x + deterministic_noise
    result = breusch_pagan_calibration_test(x, y)
    assert 0.0 <= result["p_value"] <= 1.0
    assert "heteroscedastic_at_0_05" in result
