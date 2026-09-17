from __future__ import annotations

from pathlib import Path
import sys

from . import __version__


_HELP = """UV-Vis Spectrum Studio

Usage:
  uvvis-spectrum-studio [STREAMLIT_OPTIONS]
  uvvis-spectrum-studio --version
  uvvis-spectrum-studio --help

Without --version/--help the command launches the packaged Streamlit application.
Any remaining options are forwarded to `streamlit run`, for example:
  uvvis-spectrum-studio --server.port 8502
"""


def main(argv: list[str] | None = None) -> int:
    """Run the installed application CLI.

    ``--version`` and ``--help`` are handled locally and must never start a
    Streamlit server. Other arguments are forwarded to Streamlit so advanced
    users can configure the local server using normal Streamlit options.
    """
    args = list(sys.argv[1:] if argv is None else argv)

    if "--version" in args:
        print(__version__)
        return 0
    if "--help" in args or "-h" in args:
        print(_HELP.rstrip())
        return 0

    from streamlit.web import cli as stcli

    app_path = Path(__file__).with_name("webapp.py").resolve()
    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--global.developmentMode",
        "false",
        "--browser.gatherUsageStats",
        "false",
        *args,
    ]
    result = stcli.main()
    return int(result or 0)


if __name__ == "__main__":
    raise SystemExit(main())
