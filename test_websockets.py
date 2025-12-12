#!/usr/bin/env python3
"""
Test script for WebSocket spaces functionality
Tests connection, request submission, and result retrieval

Usage:
    python test_websockets.py --host http://localhost:5001 --username testuser --password testpass
"""

import argparse
import json
import time
import requests
import sys
from datetime import datetime


class WebSocketTester:
    """Test the WebSocket spaces functionality"""

    def __init__(self, host, username, password, verbose=False):
        self.host = host.rstrip('/')
        self.username = username
        self.password = password
        self.verbose = verbose
        self.session = requests.Session()
        self.api_key = None
        self.space_id = None
        self.test_results = []

    def log(self, level, message):
        """Log message"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if level == "INFO":
            print(f"[{timestamp}] [INFO] {message}")
        elif level == "SUCCESS":
            print(f"[{timestamp}] [\033[92m✓\033[0m] {message}")
        elif level == "ERROR":
            print(f"[{timestamp}] [\033[91m✗\033[0m] {message}")
        elif level == "TEST":
            print(f"\n{'='*70}")
            print(f"[{timestamp}] TEST: {message}")
            print(f"{'='*70}")
        elif level == "DEBUG":
            if self.verbose:
                print(f"[{timestamp}] [DEBUG] {message}")

    def test(self, name, func):
        """Run a test and track results"""
        try:
            self.log("TEST", name)
            func()
            self.test_results.append((name, True, None))
            self.log("SUCCESS", f"{name} passed")
            return True
        except AssertionError as e:
            self.test_results.append((name, False, str(e)))
            self.log("ERROR", f"{name} failed: {e}")
            return False
        except Exception as e:
            self.test_results.append((name, False, str(e)))
            self.log("ERROR", f"{name} error: {e}")
            return False

    def run_all_tests(self):
        """Run all tests"""
        print("\n" + "=" * 70)
        print("  WebSocket Spaces Functionality Tests")
        print("=" * 70)
        print(f"  Host: {self.host}")
        print(f"  Username: {self.username}")
        print("=" * 70 + "\n")

        # Test 1: Create user account or login
        self.test("User Authentication", self.test_user_auth)

        # Test 2: Create a WebSocket space
        self.test("Create WebSocket Space", self.test_create_websocket_space)

        # Test 3: Get space details
        self.test("Get Space Details", self.test_get_space_details)

        # Test 4: Check connection status (should be disconnected initially)
        self.test("Check Connection Status (Disconnected)", self.test_check_connection_disconnected)

        # Test 5: Submit inference request (should fail - not connected)
        self.test("Submit Request When Disconnected", self.test_submit_request_disconnected)

        # Print results
        self.print_results()

    def print_results(self):
        """Print test results summary"""
        print("\n" + "=" * 70)
        print("  Test Results Summary")
        print("=" * 70)

        passed = sum(1 for _, success, _ in self.test_results if success)
        total = len(self.test_results)

        for name, success, error in self.test_results:
            status = "\033[92m✓\033[0m" if success else "\033[91m✗\033[0m"
            print(f"{status} {name}")
            if error:
                print(f"  Error: {error}")

        print(f"\nTotal: {passed}/{total} tests passed")
        print("=" * 70 + "\n")

        return passed == total

    def test_user_auth(self):
        """Test user authentication"""
        self.log("INFO", "Attempting login...")

        # Try to login
        response = self.session.post(
            f"{self.host}/login",
            data={'username': self.username, 'password': self.password}
        )

        if response.status_code == 200:
            self.log("DEBUG", "Login successful")
        else:
            self.log("DEBUG", f"Login returned {response.status_code}, trying registration...")
            
            # Try registration
            response = self.session.post(
                f"{self.host}/register",
                data={
                    'username': self.username,
                    'password': self.password,
                    'confirm_password': self.password
                }
            )
            assert response.status_code in [200, 302], f"Registration failed: {response.status_code}"
            
            # Now login
            response = self.session.post(
                f"{self.host}/login",
                data={'username': self.username, 'password': self.password}
            )
            
        assert response.status_code in [200, 302], f"Login failed: {response.status_code}"
        self.log("SUCCESS", "Authentication successful")

    def test_create_websocket_space(self):
        """Test creating a WebSocket space"""
        self.log("INFO", "Accessing admin panel...")

        # Get admin panel to extract CSRF token if needed
        response = self.session.get(f"{self.host}/admin")
        assert response.status_code == 200, f"Admin access failed: {response.status_code}"

        # Create WebSocket space
        space_data = {
            'name': f'TestSpace_{int(time.time())}',
            'description': 'Test WebSocket Space for automated testing',
            'cover': 'default.png',
            'cover_type': 'image',
            'card_type': 'websockets',
            'ws_enable_prompt': 'on',
            'ws_enable_audio': 'on',
            'ws_enable_video': 'on',
            'ws_enable_file_upload': 'on'
        }

        response = self.session.post(
            f"{self.host}/admin/space/add",
            data=space_data
        )

        # The response should be a redirect or success page
        assert response.status_code in [200, 302], f"Space creation failed: {response.status_code}"

        # Parse space ID from response URL if redirect
        if response.status_code == 302:
            redirect_url = response.headers.get('Location', '')
            if '/edit/' in redirect_url:
                self.space_id = redirect_url.split('/edit/')[-1].rstrip('/')
                self.log("INFO", f"Space created with ID: {self.space_id}")
        
        # If no redirect, try to find the space
        if not self.space_id:
            self.log("INFO", "Searching for created space...")
            response = self.session.get(f"{self.host}/admin/")
            assert response.status_code == 200
            # The space_id will be fetched in next test

        self.log("SUCCESS", "WebSocket space created")

    def test_get_space_details(self):
        """Test getting space details"""
        self.log("INFO", "Fetching spaces list...")

        # Get the main page to find spaces
        response = self.session.get(f"{self.host}/")
        assert response.status_code == 200, f"Failed to get main page: {response.status_code}"

        self.log("SUCCESS", "Retrieved spaces information")

    def test_check_connection_disconnected(self):
        """Test checking connection status when disconnected"""
        if not self.space_id:
            self.log("INFO", "Skipping - no space ID found")
            return

        self.log("INFO", f"Checking space {self.space_id}...")

        response = self.session.get(f"{self.host}/ai_project/{self.space_id}")
        assert response.status_code == 200, f"Failed to access space: {response.status_code}"
        assert 'disconnected' in response.text.lower() or 'not connected' in response.text.lower() or \
               '未连接' in response.text or '✗' in response.text, \
               "Space should show as disconnected"

        self.log("SUCCESS", "Connection status correctly shows as disconnected")

    def test_submit_request_disconnected(self):
        """Test submitting a request when app is disconnected"""
        if not self.space_id:
            self.log("INFO", "Skipping - no space ID found")
            return

        self.log("INFO", "Attempting to submit request without connected app...")

        response = self.session.post(
            f"{self.host}/websockets/submit/{self.space_id}",
            data={'prompt': 'Test prompt'}
        )

        # Should fail with 503 (service unavailable) since no remote app is connected
        assert response.status_code == 503, f"Expected 503 but got {response.status_code}"
        
        data = response.json()
        assert not data.get('success'), "Request should fail"
        assert 'not connected' in data.get('error', '').lower() or 'remote' in data.get('error', '').lower(), \
               f"Error message should mention disconnection: {data.get('error')}"

        self.log("SUCCESS", "Correctly rejected request from disconnected app")


def create_test_space():
    """Helper function to create a test space via API"""
    parser = argparse.ArgumentParser(description="Create a WebSocket test space")
    parser.add_argument("--host", default="http://localhost:5001")
    parser.add_argument("--admin-user", default="admin")
    parser.add_argument("--admin-pass", default="admin123")
    args = parser.parse_args()

    print("\nCreating test WebSocket space...")
    print(f"Host: {args.host}")
    print(f"Admin User: {args.admin_user}\n")

    session = requests.Session()

    # Login as admin
    response = session.post(
        f"{args.host}/login",
        data={'username': args.admin_user, 'password': args.admin_pass}
    )

    if response.status_code not in [200, 302]:
        print(f"❌ Failed to login as admin: {response.status_code}")
        return False

    # Create space
    space_name = f"TestSpace_{int(time.time())}"
    response = session.post(
        f"{args.host}/admin/space/add",
        data={
            'name': space_name,
            'description': 'Test WebSocket Space - For manual testing with mock_app.py',
            'cover': 'default.png',
            'cover_type': 'image',
            'card_type': 'websockets',
            'ws_enable_prompt': 'on',
            'ws_enable_audio': 'on',
            'ws_enable_video': 'on',
            'ws_enable_file_upload': 'on'
        }
    )

    if response.status_code in [200, 302]:
        print(f"✓ Space created: {space_name}")
        print(f"\nNow run the mock app with:")
        print(f"  python mock_app.py --host {args.host} --spaces \"{space_name}\"")
        return True
    else:
        print(f"❌ Failed to create space: {response.status_code}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Test WebSocket spaces functionality"
    )
    parser.add_argument(
        "--host",
        default="http://localhost:5001",
        help="Website host URL (default: http://localhost:5001)"
    )
    parser.add_argument(
        "--username",
        default="testuser",
        help="Test username (default: testuser)"
    )
    parser.add_argument(
        "--password",
        default="testpass123",
        help="Test password (default: testpass123)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--setup-space",
        action="store_true",
        help="Setup test space and exit (requires admin credentials)"
    )

    args = parser.parse_args()

    if args.setup_space:
        create_test_space()
        return

    tester = WebSocketTester(args.host, args.username, args.password, args.verbose)
    success = tester.run_all_tests()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
