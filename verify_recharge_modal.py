
import os
import time
from playwright.sync_api import sync_playwright, expect

def verify_recharge_flow():
    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=True)
        # We need a context with storage state if possible, but for this test we'll register a new user
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()

        try:
            # 1. Register a new user
            unique_id = int(time.time())
            username = f"testuser_{unique_id}"
            page.goto("http://127.0.0.1:5001/register")
            page.fill('input[name="username"]', username)
            page.fill('input[name="password"]', "password123")
            # Note: The actual register form DOES NOT have confirm_password field based on file inspection
            # Removing that line
            page.click('button[type="submit"]')

            # Wait for login/redirect
            page.wait_for_url("http://127.0.0.1:5001/login")

            # Login
            page.fill('input[name="username"]', username)
            page.fill('input[name="password"]', "password123")
            page.click('button[type="submit"]')

            # Wait for dashboard/profile
            page.wait_for_url("http://127.0.0.1:5001/")

            # Go to Profile page
            page.goto("http://127.0.0.1:5001/profile")

            # 2. Simulate clicking the Recharge button
            print("Injecting localStorage state to simulate pending recharge...")
            page.evaluate("""() => {
                localStorage.setItem('payment_pending', 'true');
                localStorage.setItem('payment_timestamp', Date.now().toString());
            }""")

            # Reload page to trigger the modal
            page.reload()

            # 3. Verify Modal Appears
            print("Checking for modal...")
            modal = page.locator('#recharge-confirm-modal')
            expect(modal).to_be_visible(timeout=5000)

            page.screenshot(path='/home/jules/verification/recharge_modal_visible.png')
            print("Screenshot taken: recharge_modal_visible.png")

            # 4. Click "Yes, Check Status"
            print("Clicking Check Status...")

            # Setup dialog handler first
            page.on("dialog", lambda dialog: dialog.accept())

            check_btn = page.locator('#check-status-btn')
            check_btn.click()

            # Wait a bit for the spinner/fetch
            page.wait_for_timeout(2000)

            # Take another screenshot
            page.screenshot(path='/home/jules/verification/recharge_check_flow.png')
            print("Screenshot taken: recharge_check_flow.png")

        except Exception as e:
            print(f"Test failed: {e}")
            page.screenshot(path='/home/jules/verification/failure.png')
            raise e
        finally:
            browser.close()

if __name__ == "__main__":
    verify_recharge_flow()
