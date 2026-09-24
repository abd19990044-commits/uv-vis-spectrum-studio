"""Real-browser release checks. Run with the application's test environment.

Requires playwright + installed Chromium; writes evidence to the given folder.
No test is skipped when a prerequisite or workflow fails.
"""
from pathlib import Path
import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright, expect
from scipy.special import erf

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="release_evidence/browser")
    parser.add_argument("--installed", action="store_true")
    args = parser.parse_args()
    if not args.installed:
        sys.path.insert(0, str(ROOT))
    import uvvis_studio
    from uvvis_studio.project import load_project
    if args.installed:
        assert ROOT not in Path(uvvis_studio.__file__).resolve().parents, uvvis_studio.__file__
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out/"results.json").unlink(missing_ok=True)
    x = np.arange(200., 401.)
    y = .02 + .8*np.exp(-.5*((x-270)/12)**2)
    csv = out / "reference_spectrum.csv"
    np.savetxt(csv, np.column_stack([x, y]), delimiter=",")  # deliberately headerless
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    log = (out/"server.log").open("w")
    evidence = {"version": uvvis_studio.__version__, "module": uvvis_studio.__file__,
                "mode": "installed CLI" if args.installed else "source"}
    with sync_playwright() as p:
        env = dict(os.environ, BROWSER_PATH=os.environ.get("BROWSER_PATH", p.chromium.executable_path))
        command = ([sys.executable, "-m", "uvvis_studio.cli"] if args.installed else
                   [sys.executable, "-m", "streamlit", "run", str(ROOT/"app.py")])
        server = subprocess.Popen(
            [*command,
             "--server.address=127.0.0.1", f"--server.port={port}",
             "--server.headless=true", "--browser.gatherUsageStats=false"],
            cwd=out if args.installed else ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
        )
        browser = None
        try:
            for attempt in range(100):
                if server.poll() is not None:
                    raise RuntimeError("Streamlit server exited; inspect server.log.")
                try:
                    with urllib.request.urlopen(url+"/_stcore/health", timeout=1) as response:
                        if response.read() == b"ok":
                            break
                except OSError:
                    time.sleep(.2)
            else:
                raise RuntimeError("Server health check did not pass.")
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
            evidence["browser_version"] = browser.version
            page.set_default_timeout(30000)
            expect.set_options(timeout=30000)

            def settle():
                page.wait_for_timeout(500)
                expect(page.get_by_test_id("stStatusWidget")).not_to_be_visible()
            page.goto(url)
            uploader = page.get_by_test_id("stFileUploader").filter(has_text="Load UV–Vis files")
            uploader.locator('input[type="file"]').set_input_files(str(csv))
            expect(page.get_by_test_id("stPlotlyChart").first).to_be_visible()
            expect(page.get_by_test_id("stException")).to_have_count(0)
            page.screenshot(path=str(out/"01_spectrum.png"), full_page=True)
            evidence["upload_headerless_csv"] = True
            print("PASS: headerless upload", flush=True)

            page.get_by_text("Derivative Comparison (0D vs nD)", exact=True).click()
            expect(page.get_by_text("Comparing", exact=False).first).to_be_visible()
            expect(page.get_by_test_id("stException")).to_have_count(0)
            page.screenshot(path=str(out/"02_comparison.png"), full_page=True)
            page.get_by_text("Standard Spectrum Viewer", exact=True).click()
            settle()
            page.get_by_label("Start wavelength (nm)", exact=True).fill("260")
            page.get_by_label("Start wavelength (nm)", exact=True).press("Enter")
            settle()
            expect(page.get_by_label("Start wavelength (nm)", exact=True)).to_have_value("260.00")
            page.get_by_label("End wavelength (nm)", exact=True).fill("280")
            page.get_by_label("End wavelength (nm)", exact=True).press("Enter")
            settle()
            page.get_by_role("button", name="Calculate AUC", exact=True).click()
            expect(page.get_by_test_id("stMetric").filter(has_text="Selected Interval")
                   .get_by_test_id("stMetricValue")).to_have_text("260.00 – 280.00 nm")
            metric = page.get_by_test_id("stMetric").filter(has_text="Signed AUC (Abs·nm)").first
            expect(metric).to_be_visible()
            value = float(metric.get_by_test_id("stMetricValue").inner_text())
            oracle = .02*20 + .8*12*np.sqrt(2*np.pi)*erf(10/(12*np.sqrt(2)))
            assert abs(value-oracle)/oracle < .001, (value, oracle)
            evidence["auc"] = {"observed": value, "analytic_gaussian_integral": float(oracle)}
            print("PASS: comparison and AUC reference", flush=True)
            page.get_by_role("button", name="Reset Range", exact=True).click()
            expect(page.get_by_label("Start wavelength (nm)", exact=True)).to_have_value("200.00")
            expect(page.get_by_label("End wavelength (nm)", exact=True)).to_have_value("400.00")
            settle()

            def select_derivative(label):
                combo = page.get_by_label("Derivative order", exact=True)
                combo.press("ArrowDown")
                page.get_by_role("option", name=label, exact=True).click()
                expect(combo).to_have_value(label)
                settle()

            select_derivative("Fourth derivative (4D)")
            expect(page.get_by_test_id("stMetric").filter(has_text="Signed AUC (Abs/nm³)").first).to_be_visible()
            expect(page.get_by_test_id("stException")).to_have_count(0)
            axis_title = page.locator(".js-plotly-plot").first.evaluate("e => e.layout.yaxis.title.text")
            assert "nm⁴" in axis_title, axis_title
            evidence["fourth_derivative_axis"] = axis_title
            page.screenshot(path=str(out/"03_fourth_derivative.png"), full_page=True)
            select_derivative("Original spectrum (0D)")

            page.get_by_role("tab", name="Publication Export", exact=True).click()
            page.get_by_role("button", name="Generate Publication Figures (PNG/SVG/PDF)", exact=True).click()
            png_button = page.get_by_role("button", name="📥 Download PNG (300 DPI)", exact=True)
            expect(png_button).to_be_visible(timeout=90000)
            for label, filename in [
                ("📥 Download PNG (300 DPI)", "spectrum.png"),
                ("📥 Download SVG (Vector)", "spectrum.svg"),
                ("📥 Download PDF (Vector)", "spectrum.pdf"),
            ]:
                with page.expect_download() as download:
                    page.get_by_role("button", name=label, exact=True).click()
                download.value.save_as(out/filename)
                assert (out/filename).stat().st_size > 1000
            with Image.open(out/"spectrum.png") as im:
                assert im.size == (2100, 1500), im.size
                assert abs(im.info["dpi"][0] - 300) < 1
            assert (out/"spectrum.pdf").read_bytes().startswith(b"%PDF")
            assert "<svg" in (out/"spectrum.svg").read_text()
            evidence["png_svg_pdf_export"] = True
            print("PASS: PNG, SVG, PDF downloads", flush=True)

            # Changing processing must invalidate the previously generated figures.
            select_derivative("First derivative (1D)")
            expect(png_button).to_have_count(0)
            evidence["stale_export_invalidated"] = True
            page.get_by_role("tab", name="💾 Project & export", exact=True).click()
            with page.expect_download() as download:
                page.get_by_role("button", name="Save complete project", exact=True).click()
            project_file = out/"roundtrip.uvvisproj"
            download.value.save_as(project_file)
            project = load_project(project_file.read_bytes())
            np.testing.assert_allclose(project["spectra"][0]["y"], y)
            assert project["settings"]["derivative_order"] == 1
            assert project["integrity"]["verified"]
            page2 = browser.new_page(viewport={"width": 1440, "height": 1000})
            page2.goto(url)
            page2.get_by_test_id("stFileUploader").filter(has_text="Open UV-Vis project").locator('input[type="file"]').set_input_files(str(project_file))
            expect(page2.get_by_test_id("stPlotlyChart").first).to_be_visible()
            expect(page2.get_by_test_id("stException")).to_have_count(0)
            page2.screenshot(path=str(out/"04_reopened_project.png"), full_page=True)
            evidence["project_roundtrip"] = True
            for width, height in [(1366, 768)]:
                page2.set_viewport_size({"width": width, "height": height})
                page2.screenshot(path=str(out/f"viewport_{width}.png"), full_page=True)
            evidence["status"] = "passed"
            (out/"results.json").write_text(json.dumps(evidence, indent=2))
            print(json.dumps(evidence, indent=2), flush=True)
        finally:
            if browser is not None:
                browser.close()
            server.terminate()
            server.wait(timeout=15)
            log.close()


if __name__ == "__main__":
    main()
