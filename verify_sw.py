from playwright.sync_api import sync_playwright, expect
import time

def verify_sw():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()

        print("Checking Service Worker URL...")
        # Directly navigate to the SW file to ensure it's served
        response = page.goto("http://127.0.0.1:5001/firebase-messaging-sw.js")

        if response.ok:
            print(f"Service Worker file served successfully. Status: {response.status}")
            content = page.content()
            if "importScripts" in content:
                print("Service Worker content verified.")
            else:
                print("Content mismatch.")
        else:
            print(f"Failed to serve Service Worker. Status: {response.status}")

        # Also check ads.txt while we are here
        print("Checking ads.txt...")
        response = page.goto("http://127.0.0.1:5001/ads.txt")
        if response.ok:
             print("ads.txt served successfully.")

        browser.close()

if __name__ == "__main__":
    verify_sw()
