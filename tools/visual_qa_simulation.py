from __future__ import annotations

import os
from pathlib import Path
import time
from playwright.sync_api import sync_playwright

SCREENSHOT_DIR = Path("audit_artifacts/visual")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
BASE_URL = "http://localhost:8501"


def run_visual_qa():
    print(f"Connecting to Streamlit app at {BASE_URL}...")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)

        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        page.wait_for_selector("text=UV-Vis Spectrum Studio", timeout=15000)

        # -------------------------------------------------------------
        # Workflow 1: Upload single spectrum and inspect Data & metrics
        # -------------------------------------------------------------
        print("\n--- Workflow 1: Single Spectrum Import & Metrics ---")
        caffeine_path = Path("audit_artifacts/functional/caffeine_spectrum.csv").resolve()
        spectral_uploader = page.locator('[data-testid="stFileUploader"]').filter(has_text="Load UV–Vis files")
        spectral_uploader.locator('input[type="file"]').set_input_files(str(caffeine_path))
        print("Uploaded caffeine_spectrum.csv to Spectral workspace.")
        page.wait_for_selector(".js-plotly-plot", timeout=20000)
        time.sleep(2)

        # Navigate to Data & metrics tab
        tab_metrics = page.get_by_role("tab").filter(has_text="Data & metrics")
        tab_metrics.click()
        time.sleep(2)
        wf1_metrics = SCREENSHOT_DIR / "03_workflow1_data_metrics_table.png"
        page.screenshot(path=str(wf1_metrics))
        print(f"Captured {wf1_metrics.name}")

        # -------------------------------------------------------------
        # Workflow 4: Derivative Spectroscopy & Zero Crossings
        # -------------------------------------------------------------
        print("\n--- Workflow 4: Derivative Spectroscopy ---")
        tab_deriv = page.get_by_role("tab").filter(has_text="Derivatives")
        tab_deriv.click()
        time.sleep(2)
        wf4_shot = SCREENSHOT_DIR / "04_workflow4_derivatives_tab.png"
        page.screenshot(path=str(wf4_shot))
        print(f"Captured {wf4_shot.name}")

        # -------------------------------------------------------------
        # Workflow 2: Calibration Tab & Quantitative Regression
        # -------------------------------------------------------------
        print("\n--- Workflow 2: Calibration Tab ---")
        tab_cal = page.get_by_role("tab").filter(has_text="Calibration")
        tab_cal.click()
        time.sleep(2)
        wf2_shot = SCREENSHOT_DIR / "05_workflow2_calibration_tab.png"
        page.screenshot(path=str(wf2_shot))
        print(f"Captured {wf2_shot.name}")

        # -------------------------------------------------------------
        # Workflow 6: Chemometrics & Advanced Suite
        # -------------------------------------------------------------
        print("\n--- Workflow 6: Chemometrics Suite ---")
        tab_chemo = page.get_by_role("tab").filter(has_text="Chemometrics")
        tab_chemo.click()
        time.sleep(2)
        wf6_shot = SCREENSHOT_DIR / "06_workflow6_chemometrics_suite.png"
        page.screenshot(path=str(wf6_shot))
        print(f"Captured {wf6_shot.name}")

        # -------------------------------------------------------------
        # Workflow 5: Project & Export Tab
        # -------------------------------------------------------------
        print("\n--- Workflow 5: Project & Export Tab ---")
        tab_proj = page.get_by_role("tab").filter(has_text="Project & export")
        tab_proj.click()
        time.sleep(2)
        wf5_shot = SCREENSHOT_DIR / "07_workflow5_project_export_tab.png"
        page.screenshot(path=str(wf5_shot))
        print(f"Captured {wf5_shot.name}")

        # -------------------------------------------------------------
        # Workflow 3: Multi-Spectrum Standards Series Overlay
        # -------------------------------------------------------------
        print("\n--- Workflow 3: Multi-Spectrum Standards Overlay ---")
        multi_path = Path("audit_artifacts/functional/standards_series.csv").resolve()
        spectral_uploader.locator('input[type="file"]').set_input_files(str(multi_path))
        time.sleep(4)
        tab_spectra = page.get_by_role("tab").filter(has_text="Spectra")
        tab_spectra.click()
        time.sleep(3)
        wf3_shot = SCREENSHOT_DIR / "08_workflow3_multi_standards_overlay.png"
        page.screenshot(path=str(wf3_shot))
        print(f"Captured {wf3_shot.name}")

        context.close()
        browser.close()
        print("\nAll remaining workflow screenshots captured successfully!")


if __name__ == "__main__":
    run_visual_qa()
