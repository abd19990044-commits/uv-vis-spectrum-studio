from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_app_renders_without_exception():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    at = AppTest.from_file(str(app_path), default_timeout=45)
    at.run()
    assert len(at.exception) == 0, [str(exc.value) for exc in at.exception]
