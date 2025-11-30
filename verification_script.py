from playwright.sync_api import sync_playwright
import time
import requests

BASE_URL = "http://127.0.0.1:5001"

def register_and_login(page, username):
    page.goto(f"{BASE_URL}/register")
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', "password")
    # page.fill('input[name="confirm_password"]', "password")
    page.click('button[type="submit"]')
    page.wait_for_url(f"{BASE_URL}/login")

    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', "password")
    page.click('button[type="submit"]')
    page.wait_for_url(f"{BASE_URL}/")

def verify_gpu_pool(page):
    admin_user = f"admin_pool_{int(time.time())}"
    normal_user = f"user_pool_{int(time.time())}"

    register_and_login(page, admin_user)

    return admin_user, normal_user

def promote_to_admin(username):
    import sqlite3
    import json
    import os

    # Corrected path based on ls output
    db_path = "instance/database.sqlite"

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM app_data WHERE key = 'main_db'")
    row = cursor.fetchone()
    if row:
        db_data = json.loads(row['value'])
        if username in db_data['users']:
            db_data['users'][username]['is_admin'] = True
            new_json = json.dumps(db_data)
            cursor.execute("UPDATE app_data SET value = ? WHERE key = 'main_db'", (new_json,))
            conn.commit()
    conn.close()

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        try:
            admin_user, normal_user = verify_gpu_pool(page)
            print(f"Created users: {admin_user}, {normal_user}")

            promote_to_admin(admin_user)
            print("Promoted admin")

            page.reload()

            page.goto(f"{BASE_URL}/admin/gpu-pool")
            page.screenshot(path="/home/jules/verification/admin_pool_empty.png")

            page.fill('input[name="name"]', "Test GPU L40S")
            page.fill('input[name="api_url"]', "http://example.com")
            page.fill('input[name="api_token"]', "test-token-123")
            page.click('button[type="submit"]')

            page.screenshot(path="/home/jules/verification/admin_pool_added.png")

            page.goto(f"{BASE_URL}/logout")

            register_and_login(page, normal_user)

            page.goto(f"{BASE_URL}/chat")
            time.sleep(2)

            page.screenshot(path="/home/jules/verification/user_chat_allocation.png")

            page.goto(f"{BASE_URL}/cloud-terminal")
            page.screenshot(path="/home/jules/verification/user_terminal_allocation.png")

        except Exception as e:
            print(f"Error: {e}")
            page.screenshot(path="/home/jules/verification/error.png")
        finally:
            browser.close()
