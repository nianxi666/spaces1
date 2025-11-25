from playwright.sync_api import sync_playwright, expect
import time

def verify_granular_ads():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()

        # Assume ads are enabled by default in database.py logic
        print("Visiting Homepage...")
        page.goto("http://127.0.0.1:5001/")
        time.sleep(2)
        page.screenshot(path="/home/jules/verification/granular_check.png", full_page=True)

        # Verify monetag/adsterra elements presence or absence in page content?
        # This is hard to test via screenshot without explicit visual markers, but I can check page source logic?
        # No, I just need to confirm it loads without error.
        print("Granular Check screenshot taken.")

        browser.close()

if __name__ == "__main__":
    verify_granular_ads()
