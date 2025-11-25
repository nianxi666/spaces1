from playwright.sync_api import sync_playwright, expect
import time

def verify_sw_and_mime():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()

        print("Checking Service Worker URL...")
        response = page.goto("http://127.0.0.1:5001/firebase-messaging-sw.js")

        if response.ok:
            print(f"Service Worker Status: {response.status}")
            headers = response.headers
            content_type = headers.get('content-type', '')
            print(f"Content-Type: {content_type}")

            if "javascript" in content_type:
                print("MIME type correct.")
            else:
                print(f"MIME type mismatch! Expected javascript, got {content_type}")

            content = page.content()
            if "importScripts" in content:
                print("Content verification passed.")
            else:
                print("Content verification failed.")
        else:
            print(f"Failed to fetch SW. Status: {response.status}")

        browser.close()

if __name__ == "__main__":
    verify_sw_and_mime()
