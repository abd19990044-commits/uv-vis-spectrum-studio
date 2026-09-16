import numpy as np

from uvvis_studio.project import PROJECT_VERSION, load_project, project_bytes
from uvvis_studio.workspace_state import capture_settings, restore_project_to_session


def test_project_roundtrip_preserves_raw_spectrum_and_settings():
    x = np.linspace(200.0, 400.0, 21)
    raw = np.sin(x / 40.0) + 1.2
    spectrum = {
        "name": "NAP",
        "x": x,
        "y": raw,
        "raw_y": raw.copy(),
        "analysis_y": raw * 2.0,
        "color": "#123456",
        "dash": "dash",
        "source": "nap.csv",
        "column": "Abs",
    }
    settings = {"derivative_order": 2, "smoothing_method": "Savitzky-Golay", "title": "Test"}
    data = project_bytes([spectrum], settings=settings, notes="reproducible")
    project = load_project(data)

    assert project["metadata"]["version"] == PROJECT_VERSION
    assert project["settings"] == settings
    assert project["notes"] == "reproducible"
    assert len(project["spectra"]) == 1
    restored = project["spectra"][0]
    np.testing.assert_allclose(restored["x"], x)
    np.testing.assert_allclose(restored["y"], raw)
    np.testing.assert_allclose(restored["raw_y"], raw)
    assert restored["color"] == "#123456"
    assert restored["dash"] == "dash"


def test_workspace_restore_populates_widget_state_and_curve_metadata():
    x = np.array([200.0, 201.0, 202.0])
    y = np.array([0.1, 0.2, 0.3])
    project = load_project(
        project_bytes(
            [{"name": "Curve A", "x": x, "y": y, "color": "#ABCDEF", "dash": "dot"}],
            settings={"derivative_order": 1, "linewidth": 3.2, "grid": True},
            notes="abc",
        )
    )
    state = {}
    restore_project_to_session(state, project)

    assert state["derivative_order"] == 1
    assert state["linewidth"] == 3.2
    assert state["grid"] is True
    assert state["_project_notes"] == "abc"
    assert state["project_name_0"] == "Curve A"
    assert state["project_color_0"] == "#ABCDEF"
    assert state["project_style_0"] == "Dotted"


def test_capture_settings_excludes_internal_and_complex_values():
    state = {
        "derivative_order": 2,
        "title": "Spectrum",
        "grid": False,
        "_private": "ignore",
        "calibration_table": [1, 2, 3],
    }
    captured = capture_settings(state)
    assert captured == {"derivative_order": 2, "title": "Spectrum", "grid": False}
