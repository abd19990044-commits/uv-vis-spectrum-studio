import io

import numpy as np
import pandas as pd

from uvvis_studio.io import clean_xy, read_table
from uvvis_studio.multicomponent import simultaneous_equations
from uvvis_studio.project import load_project, project_bytes
from uvvis_studio.quality import absorbance_quality, derivative_quality
from uvvis_studio.validation import inverse_prediction_interval, mandel_fitting_test, linearity_validation


def test_negative_slope_lod_loq_are_positive():
    x = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    y = 2.0 - 0.5 * x
    result = linearity_validation(x, y, sigma=0.01)
    assert result.slope < 0
    assert result.lod_33 > 0
    assert result.loq_10 > 0


def test_mandel_detects_strong_quadratic_curvature():
    x = np.linspace(0.0, 6.0, 13)
    y = 1.0 + 0.5 * x + 0.2 * x**2
    result = mandel_fitting_test(x, y)
    assert result["quadratic_improvement_significant"]
    assert result["p_value"] < 0.05


def test_inverse_prediction_interval_contains_exact_unknown():
    x = np.arange(6.0)
    y = 0.2 + 2.0 * x + np.array([0.00, 0.01, -0.01, 0.005, -0.005, 0.0])
    unknown_x = 2.5
    unknown_y = 0.2 + 2.0 * unknown_x
    result = inverse_prediction_interval(x, y, unknown_y, unknown_replicates=3)
    assert result["lower"] <= unknown_x <= result["upper"]


def test_multicomponent_conditioning_warning_and_hard_failure():
    stable = simultaneous_equations(1.0, 0.8, 100.0, 20.0, 10.0, 90.0)
    assert stable["conditioning_status"] == "acceptable"
    # Nearly collinear absorptivity columns: hard limit intentionally lowered in
    # this test so the numerical guard is deterministic.
    try:
        simultaneous_equations(
            1.0,
            1.0,
            1.0,
            1.000001,
            1.0,
            1.000002,
            condition_warning=10.0,
            condition_hard_limit=1e5,
        )
    except ValueError as exc:
        assert "ill-conditioned" in str(exc)
    else:
        raise AssertionError("Expected ill-conditioned multicomponent system to be rejected")


def test_fourth_derivative_quality_is_safe_and_explicit():
    x = np.arange(200.0, 401.0, 0.2)
    result = derivative_quality(
        x,
        order=4,
        smoothing_window_points=11,
        requested_polyorder=3,
        fwhm_nm=12.0,
    )
    assert result.effective_polyorder >= 5
    assert result.smoothing_window_points > result.effective_polyorder
    assert result.status == "caution"
    assert result.median_step_nm == pytest_approx(0.2, 1e-10)


def pytest_approx(value, tol):
    class Approx:
        def __eq__(self, other):
            return abs(float(other) - float(value)) <= tol
    return Approx()


def test_absorbance_quality_flags_high_absorbance():
    result = absorbance_quality([0.1, 0.8, 2.2])
    assert result["status"] == "severe_caution"
    assert result["warnings"]


def test_duplicate_wavelengths_are_averaged():
    df = pd.DataFrame({"nm": [200, 201, 201, 202], "A": [0.1, 0.2, 0.4, 0.5]})
    x, y = clean_xy(df, "nm", "A")
    assert x.tolist() == [200.0, 201.0, 202.0]
    assert np.allclose(y, [0.1, 0.3, 0.5])


def test_cp1252_text_file_decodes_without_replacement():
    text = "Wavelength;Absorbance\n200;0.10\n201;0.20\n"
    raw = text.encode("cp1252")
    df = read_table(io.BytesIO(raw), "spectrum.csv")
    assert list(df.columns) == ["Wavelength", "Absorbance"]


def test_project_contains_reproducibility_and_disallows_pickle_loading():
    x = np.array([200.0, 201.0, 202.0])
    y = np.array([0.1, 0.2, 0.3])
    data = project_bytes(
        [{"name": "A", "x": x, "y": y}],
        audit_trail=[{"action": "import", "parameter": "raw"}],
        analyst="Analyst",
        instrument="UV-Vis",
    )
    loaded = load_project(data)
    assert loaded["metadata"]["version"] >= 3
    assert "python" in loaded["reproducibility"]
    assert loaded["audit_trail"][0]["action"] == "import"
    assert loaded["analyst"] == "Analyst"
