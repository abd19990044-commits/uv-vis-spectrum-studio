from __future__ import annotations

import os
import socket
import subprocess
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

APP_NAME = "UVVisSpectrumStudio"
SERVER_FLAG = "--uvvis-server"
SELF_TEST_FLAG = "--uvvis-self-test"


def resource_path(relative: str) -> str:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return str(base / relative)


def app_data_dir() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP_NAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def log_path() -> Path:
    logs = app_data_dir() / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    return logs / "startup.log"


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_server(port: int, process: subprocess.Popen[bytes], timeout: float = 90.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            return False
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.75):
                return True
        except OSError:
            time.sleep(0.25)
    return False


def configure_runtime() -> None:
    bundled_chrome = Path(resource_path("vendor/chrome/chrome.exe"))
    if bundled_chrome.exists():
        os.environ["BROWSER_PATH"] = str(bundled_chrome)
    os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
    os.environ.setdefault("STREAMLIT_SERVER_FILE_WATCHER_TYPE", "none")


def run_streamlit(port: int) -> None:
    """Run Streamlit through its supported CLI parser inside the frozen child.

    Streamlit's internal bootstrap API changed across releases and may ignore
    dotted config keys supplied programmatically. The CLI parser is the stable
    path used by `streamlit run` itself, so the requested loopback address and
    dynamically selected port are applied consistently in frozen Windows builds.
    """
    configure_runtime()
    app_path = resource_path("app.py")
    with log_path().open("a", encoding="utf-8", buffering=1) as log:
        sys.stdout = log
        sys.stderr = log
        print(f"\n=== UV-Vis server start {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
        print(f"Executable: {sys.executable}")
        print(f"App path: {app_path}")
        print(f"Requested port: {port}")

        from streamlit.web import cli as stcli

        sys.argv = [
            "streamlit",
            "run",
            app_path,
            "--server.port",
            str(port),
            "--server.address",
            "127.0.0.1",
            "--server.headless",
            "true",
            "--server.fileWatcherType",
            "none",
            "--browser.gatherUsageStats",
            "false",
        ]
        stcli.main()


def start_server_process(port: int) -> tuple[subprocess.Popen[bytes], object]:
    log_file = log_path().open("ab", buffering=0)
    env = os.environ.copy()
    env["UVVIS_DESKTOP_CHILD"] = "1"
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(
        [sys.executable, SERVER_FLAG, str(port)],
        cwd=str(Path(sys.executable).resolve().parent),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=log_file,
        stderr=log_file,
        creationflags=creation_flags,
    )
    return process, log_file


def stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def packaged_self_test() -> int:
    port = find_free_port()
    server, log_file = start_server_process(port)
    try:
        if not wait_for_server(port, server, timeout=90.0):
            return 2
        marker = os.environ.get("UVVIS_SELF_TEST_MARKER")
        if marker:
            Path(marker).write_text(f"ok:{port}\n", encoding="utf-8")
        return 0
    finally:
        stop_process(server)
        log_file.close()


def main() -> None:
    port = find_free_port()
    server, log_file = start_server_process(port)

    try:
        if not wait_for_server(port, server):
            exit_code = server.poll()
            raise RuntimeError(
                "The local UV-Vis server could not be started. "
                f"Exit code: {exit_code}. Diagnostic log: {log_path()}"
            )

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
        except Exception as exc:
            with log_path().open("a", encoding="utf-8") as log:
                print(f"WebView fallback: {exc!r}", file=log)
            webbrowser.open(url, new=1)
            while server.poll() is None:
                time.sleep(0.5)
    finally:
        stop_process(server)
        log_file.close()


def entrypoint() -> None:
    if len(sys.argv) >= 3 and sys.argv[1] == SERVER_FLAG:
        run_streamlit(int(sys.argv[2]))
        return
    if len(sys.argv) >= 2 and sys.argv[1] == SELF_TEST_FLAG:
        raise SystemExit(packaged_self_test())
    main()


if __name__ == "__main__":
    entrypoint()
