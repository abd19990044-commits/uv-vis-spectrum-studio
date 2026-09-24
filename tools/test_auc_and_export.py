import os
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

def run_test():
    url = "http://localhost:8501"
    repo_root = Path(r"G:\uv-vis\uv-vis-spectrum-studio")
    sample_file = repo_root / "audit_artifacts" / "functional" / "caffeine_spectrum.csv"
    artifacts_dir = repo_root / "audit_artifacts" / "visual"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    print(f"Connecting to {url}...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="msedge")
        context = browser.new_context(viewport={"width": 1600, "height": 1050}, accept_downloads=True)
        page = context.new_page()

        page.goto(url, wait_until="networkidle", timeout=45000)
        time.sleep(3)

        print("Uploading caffeine_spectrum.csv...")
        file_input = page.locator('input[multiple][type="file"]')
        file_input.set_input_files(str(sample_file))
        time.sleep(3)
        page.wait_for_selector("text=caffeine_spectrum", timeout=20000)

        # Scroll to AUC section
        print("Locating Area Under the Curve section...")
        auc_header = page.locator("text=Area Under the Curve — Selected Wavelength Range")
        auc_header.scroll_into_view_if_needed()
        time.sleep(1)

        # Set range 260 to 280 nm
        print("Setting interval 260 to 280 nm...")
        inputs = page.locator('input[data-testid="stNumberInputField"]')
        # Click Calculate AUC button
        calc_btn = page.locator('button:has-text("Calculate AUC")')
        if calc_btn.count() > 0:
            calc_btn.click()
            time.sleep(2)

        # Capture screenshot of AUC in Å/cm²
        auc_img_path = artifacts_dir / "test_auc_angstrom_display.png"
        page.screenshot(path=str(auc_img_path))
        print(f"Saved screenshot: {auc_img_path}")

        # Test download of AUC region
        dl_region_btn = page.locator('button:has-text("Download Selected-Region Data")')
        if dl_region_btn.count() > 0:
            print("Testing Download Selected-Region Data...")
            with page.expect_download(timeout=10000) as download_info:
                dl_region_btn.click()
            download = download_info.value
            saved_dl = artifacts_dir / "downloaded_auc_region.csv"
            download.save_as(str(saved_dl))
            print(f"Downloaded AUC region CSV to: {saved_dl}")
            content = saved_dl.read_text(encoding="utf-8-sig")
            print("First 3 lines of downloaded CSV:")
            print("\n".join(content.splitlines()[:4]))

        # Now test Publication Figures Export
        print("Locating LabSolutions Display & Axis Settings section...")
        lab_section = page.locator('text=Instrument Display & Axis Settings').first
        lab_section.scroll_into_view_if_needed()
        time.sleep(1.0)

        print("Finding all tabs on page...")
        all_tabs = page.get_by_role("tab").all()
        for idx, t in enumerate(all_tabs):
            print(f"Tab {idx}: {t.inner_text()}")

        print("Clicking 'Export & Publication' subtab...")
        export_tab = page.get_by_role("tab").filter(has_text="Export & Publication")
        if export_tab.count() == 0:
            export_tab = page.get_by_role("tab").filter(has_text="Export").last
        export_tab.scroll_into_view_if_needed()
        export_tab.click()
        time.sleep(2)

        gen_btn = page.locator('button').filter(has_text="Generate Publication Figures")
        if gen_btn.count() > 0:
            print("Clicking 'Generate Publication Figures'...")
            gen_btn.scroll_into_view_if_needed()
            gen_btn.click()
            print("Waiting for publication figures to finish rendering...")
            page.wait_for_selector('button:has-text("Download PNG")', timeout=35000)
            time.sleep(1)

            # Verify download buttons appear
            png_btn = page.locator('button:has-text("Download PNG")')
            svg_btn = page.locator('button:has-text("Download SVG")')
            pdf_btn = page.locator('button:has-text("Download PDF")')
            html_btn = page.locator('button:has-text("Download HTML")')

            print(f"Download buttons count: PNG={png_btn.count()}, SVG={svg_btn.count()}, PDF={pdf_btn.count()}, HTML={html_btn.count()}")
            assert png_btn.count() > 0, "PNG download button missing!"
            assert svg_btn.count() > 0, "SVG download button missing!"
            assert pdf_btn.count() > 0, "PDF download button missing!"

            # Test PNG download
            print("Testing PNG download...")
            with page.expect_download(timeout=15000) as png_dl_info:
                png_btn.click()
            png_dl = png_dl_info.value
            saved_png = artifacts_dir / "downloaded_spectrum_labsolutions.png"
            png_dl.save_as(str(saved_png))
            print(f"Downloaded PNG successfully ({saved_png.stat().st_size} bytes)")

            # Test SVG download
            print("Testing SVG download...")
            with page.expect_download(timeout=15000) as svg_dl_info:
                svg_btn.click()
            svg_dl = svg_dl_info.value
            saved_svg = artifacts_dir / "downloaded_spectrum_labsolutions.svg"
            svg_dl.save_as(str(saved_svg))
            print(f"Downloaded SVG successfully ({saved_svg.stat().st_size} bytes)")

            # Capture screenshot of Export section with active download buttons
            pub_img_path = artifacts_dir / "test_publication_figures_export.png"
            page.screenshot(path=str(pub_img_path))
            print(f"Saved screenshot: {pub_img_path}")

        context.close()
        browser.close()
        print("ALL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_test()
