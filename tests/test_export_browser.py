from __future__ import annotations

from pathlib import Path

import uvvis_studio.export as export


def test_configure_publication_browser_prefers_explicit_path(tmp_path, monkeypatch):
    browser = tmp_path / "chromium"
    browser.write_text("test", encoding="utf-8")
    monkeypatch.setenv("BROWSER_PATH", str(browser))
    monkeypatch.setattr(export, "_runtime_roots", lambda: [])
    monkeypatch.setattr(export, "_system_browser", lambda: None)

    assert export.configure_publication_browser() == str(browser.resolve())


def test_configure_publication_browser_falls_back_to_system_path(tmp_path, monkeypatch):
    browser = tmp_path / "chromium"
    browser.write_text("test", encoding="utf-8")
    monkeypatch.delenv("BROWSER_PATH", raising=False)
    monkeypatch.setattr(export, "_runtime_roots", lambda: [])
    monkeypatch.setattr(export.shutil, "which", lambda name: str(browser) if name == "chromium" else None)

    assert export.configure_publication_browser() == str(browser.resolve())
    assert export.os.environ["BROWSER_PATH"] == str(browser.resolve())


def test_system_browser_returns_none_when_path_has_no_supported_browser(monkeypatch):
    monkeypatch.setattr(export.shutil, "which", lambda name: None)
    assert export._system_browser() is None
