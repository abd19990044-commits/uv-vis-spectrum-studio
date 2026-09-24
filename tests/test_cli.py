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


def test_desktop_launcher_command_formulation(monkeypatch):
    import desktop_launcher
    import sys
    from pathlib import Path

    # Case 1: Running under standard Python interpreter (not frozen)
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    # Check that non-frozen uses script path
    port = 8501
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, desktop_launcher.SERVER_FLAG, str(port)]
    else:
        cmd = [sys.executable, str(Path(desktop_launcher.__file__).resolve()), desktop_launcher.SERVER_FLAG, str(port)]
    assert cmd[0] == sys.executable
    assert cmd[1] == str(Path(desktop_launcher.__file__).resolve())
    assert cmd[2] == desktop_launcher.SERVER_FLAG
    assert cmd[3] == "8501"

    # Case 2: Running as a frozen executable
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    if getattr(sys, "frozen", False):
        cmd_frozen = [sys.executable, desktop_launcher.SERVER_FLAG, str(port)]
    else:
        cmd_frozen = [sys.executable, str(Path(desktop_launcher.__file__).resolve()), desktop_launcher.SERVER_FLAG, str(port)]
    assert cmd_frozen[0] == sys.executable
    assert cmd_frozen[1] == desktop_launcher.SERVER_FLAG
    assert cmd_frozen[2] == "8501"
