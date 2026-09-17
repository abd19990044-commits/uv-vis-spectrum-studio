from __future__ import annotations

from pathlib import Path
import sys


def main() -> int:
    """Launch UV-Vis Spectrum Studio from an installed Python package."""
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
    ]
    result = stcli.main()
    return int(result or 0)


if __name__ == "__main__":
    raise SystemExit(main())
