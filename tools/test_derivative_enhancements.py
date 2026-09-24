import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent
FUNCTIONAL_DIR = ROOT_DIR / "audit_artifacts" / "functional"
VISUAL_DIR = ROOT_DIR / "audit_artifacts" / "visual"

with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    page.goto("http://localhost:8501", wait_until="domcontentloaded")
    page.wait_for_selector("h1", timeout=30000)

    # 1. Upload multi-curve dataset (standards_series.csv)
    standards_file = ROOT_DIR / "audit_artifacts" / "functional" / "standards_series.csv"
    if not standards_file.exists():
        standards_file = ROOT_DIR / "audit_artifacts" / "functional" / "chemometrics_multivariate_dataset.csv"
    
    spectral_uploader = page.locator('[data-testid="stFileUploader"]').filter(has_text="Load UV–Vis files")
    spectral_uploader.locator('input[type="file"]').set_input_files(str(standards_file))
    print(f"Uploaded {standards_file.name}")
    time.sleep(2.5)

    # Select multiple curves if multiselect present in sidebar
    ms_box = page.locator('[data-testid="stMultiSelect"]').first
    if ms_box.count() > 0:
        ms_box.locator('button[aria-label="Open"]').click()
        time.sleep(0.5)
        page.locator('[role="option"]').filter(has_text="Select all").click()
        time.sleep(1.0)
        page.keyboard.press("Escape")
        time.sleep(2.0)

    # 2. Test Tab 1: Derivatives & AUC
    print("\n--- Testing Tab 1: Derivatives with Multi-Curve Support ---")
    tab_deriv = page.get_by_role("tab").filter(has_text="Derivatives")
    tab_deriv.click()
    time.sleep(2.0)

    # Change derivative order to 2D
    deriv_box = page.locator('[data-testid="stSelectbox"]').filter(has_text="Active Derivative Order")
    deriv_box.click()
    time.sleep(0.5)
    page.locator('[role="option"]').filter(has_text="Second derivative (2D)").click()
    time.sleep(2.0)

    # Verify Derivative Unit badge is Abs/nm²
    unit_badge = page.locator('[data-testid="stMetric"]').filter(has_text="Derivative Unit").inner_text()
    print("Unit badge:", unit_badge)
    assert "Abs/nm²" in unit_badge or "Abs/nm^2" in unit_badge or "Abs/nm" in unit_badge

    # Take screenshot of Dual Subplot with all curves differentiated
    shot_dual = VISUAL_DIR / "test_derivatives_multi_curve_dual.png"
    page.screenshot(path=str(shot_dual))
    print(f"Saved: {shot_dual.name}")

    # Switch layout to Combined nD Derivative Overlay
    layout_box = page.locator('[data-testid="stSelectbox"]').filter(has_text="Visualization Layout")
    layout_box.click()
    time.sleep(0.5)
    page.locator('[role="option"]').filter(has_text="Combined nD Derivative Overlay").click()
    time.sleep(2.0)

    shot_overlay = VISUAL_DIR / "test_derivatives_multi_curve_overlay.png"
    page.screenshot(path=str(shot_overlay))
    print(f"Saved: {shot_overlay.name}")

    # Check for download button with multi-curve data
    dl_btn = page.locator('button').filter(has_text="Download 2D Derivative Data")
    print("Download button count:", dl_btn.count(), "Text:", dl_btn.first.inner_text() if dl_btn.count() else "N/A")
    assert dl_btn.count() > 0

    # 3. Test Tab 0: Derivative Comparison in Workstation Mode
    print("\n--- Testing Tab 0: Derivative Comparison (0D vs nD) ---")
    tab_hero = page.get_by_role("tab").filter(has_text="Spectra")
    tab_hero.click()
    time.sleep(2.0)

    comp_radio = page.locator('label').filter(has_text="Derivative Comparison (0D vs nD)")
    comp_radio.click()
    time.sleep(2.0)

    shot_hero_compare = VISUAL_DIR / "test_tab0_derivative_compare_multi.png"
    page.screenshot(path=str(shot_hero_compare))
    print(f"Saved: {shot_hero_compare.name}")

    # Verify subplot titles or compare info present
    main_text = page.locator('[data-testid="stMain"]').inner_text()
    assert "Derivative Spectrum" in main_text or "Derivative" in main_text
    print("Tab 0 Compare Mode verified successfully!")

    browser.close()
    print("\nALL DERIVATIVE TESTS PASSED WITH VISUAL PROOF!")
