from __future__ import annotations

import multiprocessing as mp
import os
import socket
import sys
import time
import webbrowser
from pathlib import Path

import numpy  # noqa: F401
import pandas  # noqa: F401
import plotly  # noqa: F401
import scipy  # noqa: F401
import streamlit  # noqa: F401
import uvvis_studio  # noqa: F401
from streamlit.web import bootstrap


def resource_path(relative: str) -> str:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return str(base / relative)


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_server(port: int, timeout: float = 35.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def run_streamlit(port: int) -> None:
    app_path = resource_path("app.py")
    bundled_chrome = Path(resource_path("vendor/chrome/chrome.exe"))
    if bundled_chrome.exists():
        os.environ["BROWSER_PATH"] = str(bundled_chrome)
    os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
    bootstrap.run(
        app_path,
        False,
        [],
        {
            "server.port": port,
            "server.address": "127.0.0.1",
            "server.headless": True,
            "browser.gatherUsageStats": False,
            "global.developmentMode": False,
        },
    )


def main() -> None:
    port = find_free_port()
    server = mp.Process(target=run_streamlit, args=(port,), daemon=True)
    server.start()

    if not wait_for_server(port):
        if server.is_alive():
            server.terminate()
        raise RuntimeError("The local UV-Vis server could not be started.")

    url = f"http://127.0.0.1:{port}"
    try:
        import webview

        webview.create_window(
            "UV-Vis Spectrum Studio",
            url,
            width=1440,
            height=900,
            min_size=(1050, 680),
            background_color="#f7f9fc",
            text_select=True,
        )
        webview.start(debug=False, private_mode=False)
    except Exception:
        webbrowser.open(url, new=1)
        try:
            server.join()
        except KeyboardInterrupt:
            pass
    finally:
        if server.is_alive():
            server.terminate()
            server.join(timeout=3)


if __name__ == "__main__":
    mp.freeze_support()
    main()
