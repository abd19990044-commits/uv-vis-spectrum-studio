from __future__ import annotations

from uvvis_studio import __version__
from uvvis_studio.cli import main


def test_cli_version_does_not_launch_streamlit(capsys):
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == __version__


def test_cli_help_does_not_launch_streamlit(capsys):
    assert main(["--help"]) == 0
    text = capsys.readouterr().out
    assert "UV-Vis Spectrum Studio" in text
    assert "--version" in text
    assert "STREAMLIT_OPTIONS" in text
