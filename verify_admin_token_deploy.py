from playwright.sync_api import sync_playwright, expect
import time

def verify_admin_token_deploy(page):
    print("Navigating to login...")
    page.goto("http://127.0.0.1:5001/login")
    page.fill("input[name='username']", "admin")
    page.fill("input[name='password']", "admin")
    page.click("button[type='submit']")
    page.wait_for_url("http://127.0.0.1:5001/")
    print("Logged in.")

    print("Navigating to Cloud Terminal...")
    page.goto("http://127.0.0.1:5001/cloud-terminal")

    # Verify token input is GONE
    expect(page.locator("#cloud-terminal-token")).not_to_be_visible()
    print("Token input is hidden/removed.")

    # Open deploy modal
    page.click("#open-deploy-modal")
    expect(page.locator("#deploy-modal")).to_be_visible()
    print("Modal opened.")

    # Click Deploy
    page.click("#deploy-submit-button")
    print("Deploy button clicked.")

    # Check for 'Running' status
    status_badge = page.locator("#terminal-status-badge")
    expect(status_badge).to_contain_text("运行中", timeout=10000)
    print("Status badge changed to 'Running'.")

    # Check log output
    output_el = page.locator("#cloud-terminal-output")

    # Wait for config log which proves token was loaded from DB and save-auth-config is running
    # "Configuring authentication..."
    expect(output_el).to_contain_text("Configuring authentication...", timeout=10000)
    print("Authentication configuration started.")

    # Check for success (since we used REAL token via admin API)
    # It might fail on upload/build if project structure is empty or invalid, but Auth should pass.
    # Real deployment takes time. We just want to verify it goes past Auth.

    # Wait for "Running deployment command..."
    expect(output_el).to_contain_text("Running deployment command...", timeout=30000)
    print("Auth successful. Deployment command running.")

    page.screenshot(path="/home/jules/verification/admin_token_deploy.png")
    print("Screenshot taken.")

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            verify_admin_token_deploy(page)
        except Exception as e:
            print(f"Verification failed: {e}")
            page.screenshot(path="/home/jules/verification/admin_token_failure.png")
        finally:
            browser.close()
