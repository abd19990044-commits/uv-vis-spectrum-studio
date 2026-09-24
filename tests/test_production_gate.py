from io import BytesIO
from pathlib import Path
import zipfile

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from uvvis_studio.analysis import auc_unit, baseline_als
from uvvis_studio.chemometrics import regression_analysis
from uvvis_studio.chemometrics_advanced import kennard_stone, spxy
from uvvis_studio.io import clean_xy, detect_wavelength_column, read_table
from uvvis_studio.project import _validated_spectrum_arrays, _validate_zip_archive, load_project, project_bytes
from uvvis_studio.quantitation import breusch_pagan_calibration_test, weighted_linear_calibration
from uvvis_studio.validation import inverse_prediction_interval, lack_of_fit_test, linearity_validation, mandel_fitting_test
from uvvis_studio.workspace_state import capture_settings, restore_project_to_session


@pytest.mark.parametrize("scale", [1e-9, 1., 1e9])
def test_regression_is_invariant_to_concentration_units(scale):
    x = np.arange(1., 8.)
    y = np.array([1., 2.1, 2.9, 4.2, 4.8, 6.5, 6.7])
    oracle = linearity_validation(x, y)
    fit = linearity_validation(x * scale, y)
    assert fit.slope * scale == pytest.approx(oracle.slope)
    assert fit.slope_se * scale == pytest.approx(oracle.slope_se)
    assert fit.intercept == pytest.approx(oracle.intercept)
    base_w = weighted_linear_calibration(x, y, weighting="1/x")
    fit_w = weighted_linear_calibration(x * scale, y, weighting="1/x")
    np.testing.assert_allclose(fit_w.predicted, base_w.predicted)


@pytest.mark.parametrize("scale", [1e-8, 1., 1e8])
def test_statistical_diagnostics_are_invariant_to_response_units(scale):
    x = np.arange(1., 8.)
    y = np.array([1., 2.1, 2.9, 4.2, 4.8, 6.5, 6.7])
    assert mandel_fitting_test(x, y * scale)["f"] == pytest.approx(mandel_fitting_test(x, y)["f"])
    assert breusch_pagan_calibration_test(x, y * scale)["lm"] == pytest.approx(breusch_pagan_calibration_test(x, y)["lm"])


def test_zero_pure_error_does_not_claim_significant_lack_of_fit():
    result = lack_of_fit_test([0, 0, 1, 1, 2, 2], [0, 0, 1, 1, 2, 2])
    assert result["status"] == "undefined_zero_pure_error"
    assert np.isnan(result["p_value"])
    assert np.isnan(linearity_validation([0, 1, 2], [1, 1, 1]).r2)


@pytest.mark.parametrize("raw,name", [
    (b"190,0.1\n191,0.2\n192,0.3\n", "headerless.csv"),
    (b"nm;Abs\n190;0,1\n191;0,2\n192;0,3\n", "decimal.csv"),
    (b"190\t0.1\n191\t0.2\n192\t0.3\n", "headerless.tsv"),
])
def test_import_preserves_first_reading_and_decimal_comma(raw, name):
    frame = read_table(BytesIO(raw), name)
    xcol = detect_wavelength_column(frame)
    x, y = clean_xy(frame, xcol, frame.columns[1])
    np.testing.assert_equal(x, [190, 191, 192])
    np.testing.assert_allclose(y, [.1, .2, .3])


def test_nested_array_shape_is_checked_before_allocation():
    forged = BytesIO()
    np.lib.format.write_array_header_1_0(
        forged, {"descr": "<f8", "fortran_order": False, "shape": (10**12,)})
    payload = BytesIO()
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("x.npy", forged.getvalue())
        archive.writestr("y.npy", forged.getvalue())
    with pytest.raises(ValueError, match="points"):
        _validated_spectrum_arrays(payload.getvalue(), 100*1024*1024)


def test_nested_archive_size_limit_is_enforced():
    payload = BytesIO()
    np.savez_compressed(payload, x=np.zeros(1024), y=np.zeros(1024))
    with pytest.raises(ValueError, match="uncompressed size"):
        _validated_spectrum_arrays(payload.getvalue(), 1000)


def test_duplicate_archive_member_names_rejected():
    payload = BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("project.json", "{}")
        with pytest.warns(UserWarning):
            archive.writestr("project.json", "{}")
    with zipfile.ZipFile(payload) as archive:
        with pytest.raises(ValueError, match="duplicate"):
            _validate_zip_archive(archive)


def test_constant_spectra_split_has_unique_indices():
    X = np.zeros((8, 4))
    for train, test in [kennard_stone(X, 5), spxy(X, np.zeros(8), 5)]:
        assert len(set(train)) == 5
        assert set(train).isdisjoint(test)
        assert len(train) + len(test) == 8


def test_spxy_invariant_to_overall_x_and_y_unit_scaling():
    rng = np.random.default_rng(327)
    X = rng.normal(size=(12, 10))
    y = rng.normal(size=12)
    np.testing.assert_equal(spxy(X, y, 8)[0], spxy(X*1e6, y*1e-8, 8)[0])


@pytest.mark.parametrize("model", ["PLS", "PCR"])
def test_basic_regression_uses_smallest_training_fold(model):
    rng = np.random.default_rng(44)
    X = rng.normal(size=(8, 20))
    result = regression_analysis(X, X[:, 0], model, n_components=15, cv_folds=3)
    assert np.isfinite(result.rmse_cv)


def test_blank_als_and_normalized_units():
    np.testing.assert_allclose(baseline_als(np.zeros(20)), 0, atol=1e-12)
    assert auc_unit(0, "1/nm") == "dimensionless"
    assert auc_unit(2, "1/nm") == "1/nm^2"


def test_workspace_restores_axes_and_widget_aliases():
    settings = {"auc_min": 250., "auc_max": 280., "grid": False,
                "x_auto": False, "xmin_disp": 245., "xmax_disp": 290.}
    state = {"input_auc_min": 999., "lab_grid": True, "_pub_fig_ready": True}
    restore_project_to_session(state, {"settings": settings})
    assert state["input_auc_min"] == 250.
    assert state["lab_grid"] is False
    assert state["_pub_fig_ready"] is False
    assert capture_settings(state) == settings


def test_ui_compare_auc_reset_and_unit_conversion():
    app = Path(__file__).resolve().parents[1] / "app.py"
    x = np.linspace(200, 400, 101)
    y = .01 + np.exp(-((x - 270)/20)**2)
    at = AppTest.from_file(str(app), default_timeout=60)
    project = load_project(project_bytes([{"name": "QA spectrum", "x": x, "y": y}]))
    restore_project_to_session(at.session_state, project)
    at.run()
    assert not at.exception
    at.radio(key="view_mode_selector").set_value("Derivative Comparison (0D vs nD)").run()
    assert not at.exception
    at.radio(key="view_mode_selector").set_value("Standard Spectrum Viewer").run()
    at.number_input(key="input_auc_min").set_value(251.)
    at.number_input(key="input_auc_max").set_value(279.)
    next(b for b in at.button if b.label == "Calculate AUC").click().run()
    assert not at.exception
    assert at.session_state["auc_min"] == 251.
    next(b for b in at.button if b.label == "Reset Range").click().run()
    assert not at.exception
    assert at.number_input(key="input_auc_min").value == 200.
    at.selectbox(key="conversion").set_value("%Transmittance → Absorbance").run()
    assert not at.exception
    assert not any("Signed AUC (%T" in metric.label for metric in at.metric)


def test_inverse_prediction_invariant_to_small_response_units():
    x = np.arange(1., 8.)
    y = np.array([1., 2.1, 2.9, 4.2, 4.8, 6.5, 6.7])
    base = inverse_prediction_interval(x, y, 3.5)
    scaled = inverse_prediction_interval(x, y * 1e-18, 3.5e-18)
    for key in ("concentration", "standard_error", "lower", "upper"):
        assert scaled[key] == pytest.approx(base[key])


def test_packaged_streamlit_script_executes_without_relative_import_error():
    import uvvis_studio
    at = AppTest.from_file(str(Path(uvvis_studio.__file__).with_name("webapp.py")), default_timeout=60).run()
    assert not at.exception


def test_integrity_manifest_must_cover_metadata():
    import json
    original = project_bytes([{"x": [200, 201], "y": [.1, .2]}])
    with zipfile.ZipFile(BytesIO(original)) as z:
        members = {name: z.read(name) for name in z.namelist()}
    manifest = json.loads(members["manifest.json"])
    del manifest["members"]["project.json"]
    members["manifest.json"] = json.dumps(manifest).encode()
    result = BytesIO()
    with zipfile.ZipFile(result, "w") as z:
        for name, payload in members.items(): z.writestr(name, payload)
    with pytest.raises(ValueError, match="cover every"):
        load_project(result.getvalue())


def test_png_resolution_scales_typography_with_the_figure(monkeypatch):
    from PIL import Image
    import plotly.graph_objects as go
    from uvvis_studio import export
    calls = []
    def render(self, **kwargs):
        calls.append(kwargs)
        out = BytesIO()
        Image.new("RGB", (round(kwargs["width"]*kwargs["scale"]),
                          round(kwargs["height"]*kwargs["scale"]))).save(out, format="PNG")
        return out.getvalue()
    monkeypatch.setattr(go.Figure, "to_image", render)
    monkeypatch.setattr(export, "configure_publication_browser", lambda: None)
    for dpi in (150, 300, 600):
        raw = export.figure_png_bytes(go.Figure(), 7, 5, dpi)
        with Image.open(BytesIO(raw)) as im:
            assert im.size == (7*dpi, 5*dpi)
            assert im.info["dpi"][0] == pytest.approx(dpi, abs=.02)
    assert len({(c["width"], c["height"]) for c in calls}) == 1
    assert calls[-1]["scale"] / calls[0]["scale"] == 4


@pytest.mark.parametrize("settings", [
    {"derivative_order": 7}, {"window": "eleven"}, {"norm": "invented"},
    {"auc_min": float("nan")}, {"pub_fig_w": -1}, {"grid": "false"},
])
def test_project_rejects_invalid_settings_before_widget_construction(settings):
    with pytest.raises(ValueError, match="Invalid project setting"):
        load_project(project_bytes([{"x": [200, 201], "y": [.1, .2]}], settings=settings))
