import asyncio
import json
import secrets
import uuid
from typing import Any

import websockets


DEFAULT_WS_SHELL_TIMEOUT_SECONDS = 30


def ensure_ws_shell_token(space: dict) -> str:
    token = (space.get('ws_shell_token') or '').strip()
    if token:
        return token
    token = secrets.token_urlsafe(18)
    space['ws_shell_token'] = token
    return token


def parse_ws_shell_commands(text: str) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    if not text:
        return commands

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue

        if '::' in line:
            label, command = line.split('::', 1)
        elif '|' in line:
            label, command = line.split('|', 1)
        else:
            label, command = line, line

        label = label.strip()
        command = command.strip()
        if not command:
            continue

        commands.append({
            'id': str(uuid.uuid4()),
            'label': label or command,
            'command': command,
        })

    return commands


def commands_to_text(commands: Any) -> str:
    if not isinstance(commands, list):
        return ''

    lines: list[str] = []
    for entry in commands:
        if not isinstance(entry, dict):
            continue
        label = (entry.get('label') or '').strip()
        command = (entry.get('command') or '').strip()
        if not command:
            continue
        if not label or label == command:
            lines.append(command)
        else:
            lines.append(f"{label}::{command}")

    return "\n".join(lines)


async def _run_ws_shell_command(
    target_url: str,
    shared_token: str,
    command: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    payload = {
        'type': 'run',
        'token': shared_token,
        'command': command,
    }

    async with websockets.connect(target_url, open_timeout=timeout_seconds) as websocket:
        await websocket.send(json.dumps(payload, ensure_ascii=False))
        response_raw = await asyncio.wait_for(websocket.recv(), timeout=timeout_seconds)

    try:
        response = json.loads(response_raw)
    except json.JSONDecodeError:
        response = {
            'success': False,
            'error': 'Invalid response from controlled endpoint',
            'raw': response_raw,
        }

    return response


def run_ws_shell_command(
    target_url: str,
    shared_token: str,
    command: str,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    timeout = timeout_seconds or DEFAULT_WS_SHELL_TIMEOUT_SECONDS

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run_ws_shell_command(target_url, shared_token, command, timeout))
    finally:
        try:
            loop.close()
        except Exception:
            pass
