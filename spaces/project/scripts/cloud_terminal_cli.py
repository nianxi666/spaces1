#!/usr/bin/env python3
"""
Simple CLI helper to exercise the cloud terminal APIs without opening the UI.

Example usage:
    python scripts/cloud_terminal_cli.py --username alice --command "ls"
    python scripts/cloud_terminal_cli.py --username alice --list-apps
"""
import argparse
import getpass
import json
import sys
from urllib.parse import urljoin

import requests


def parse_args():
    parser = argparse.ArgumentParser(description="Interact with cloud terminal APIs via CLI.")
    parser.add_argument("--base-url", default="http://127.0.0.1:5000", help="Flask server base URL")
    parser.add_argument("--username", required=True, help="Web portal username")
    parser.add_argument("--password", help="Web portal password (omit to prompt securely)")
    parser.add_argument("--list-apps", action="store_true", help="List custom GPU apps via backend API")
    parser.add_argument("--command", help="Command to run through the cloud terminal proxy")
    parser.add_argument("--target", help="Target name to run against (must match UI chip)")
    parser.add_argument("--target-url", help="Explicit GPU run URL to execute against")
    return parser.parse_args()


def login(session, base_url, username, password):
    login_url = urljoin(base_url.rstrip("/") + "/", "login")
    resp = session.post(login_url, data={"username": username, "password": password}, allow_redirects=True)
    if resp.status_code >= 400:
        return False, f"Login request failed with status {resp.status_code}"
    if "session" not in session.cookies:
        return False, "Login unsuccessful, session cookie missing"
    return True, None


def list_apps(session, base_url):
    apps_url = urljoin(base_url.rstrip("/") + "/", "api/cloud-terminal/apps")
    resp = session.post(apps_url, json={})
    try:
        payload = resp.json()
    except ValueError:
        payload = {"success": False, "error": resp.text}
    return resp.status_code, payload

def run_command(session, base_url, command, target=None, target_url=None):
    run_url = urljoin(base_url.rstrip("/") + "/", "api/cloud-terminal/run")
    body = {"command": command}
    if target:
        body["target"] = target
    if target_url:
        body["target_url"] = target_url
    resp = session.post(run_url, json=body)
    try:
        payload = resp.json()
    except ValueError:
        payload = {"success": False, "error": resp.text}
    return resp.status_code, payload


def main():
    args = parse_args()
    if not args.list_apps and not args.command:
        print("At least one action is required (--list-apps or --command).", file=sys.stderr)
        return 1

    password = args.password or getpass.getpass(f"Password for {args.username}: ")

    session = requests.Session()
    ok, error = login(session, args.base_url, args.username, password)
    if not ok:
        print(f"[login] {error}", file=sys.stderr)
        return 1

    exit_code = 0
    if args.list_apps:
        status, payload = list_apps(session, args.base_url)
        print("[list-apps] HTTP", status)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if status >= 400 or not payload.get("success"):
            exit_code = 1

    if args.command:
        status, payload = run_command(session, args.base_url, args.command, args.target, args.target_url)
        print("[run] HTTP", status)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if status >= 400 or not payload.get("success"):
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
