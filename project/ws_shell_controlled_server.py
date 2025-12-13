import argparse
import asyncio
import json
import subprocess
from typing import Any

import websockets


async def handle_client(websocket, shared_token: str | None):
    async for raw_message in websocket:
        try:
            payload = json.loads(raw_message)
        except json.JSONDecodeError:
            await websocket.send(json.dumps({'success': False, 'error': 'Invalid JSON'}))
            continue

        if not isinstance(payload, dict) or payload.get('type') != 'run':
            await websocket.send(json.dumps({'success': False, 'error': 'Unsupported message'}))
            continue

        token = (payload.get('token') or '').strip()
        if shared_token and token != shared_token:
            await websocket.send(json.dumps({'success': False, 'error': 'Unauthorized'}))
            continue

        command = (payload.get('command') or '').strip()
        if not command:
            await websocket.send(json.dumps({'success': False, 'error': 'Missing command'}))
            continue

        try:
            completed = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=60,
            )

            result: dict[str, Any] = {
                'success': True,
                'exit_code': completed.returncode,
                'stdout': completed.stdout,
                'stderr': completed.stderr,
            }
        except subprocess.TimeoutExpired:
            result = {'success': False, 'error': 'Command timed out'}
        except Exception as exc:
            result = {'success': False, 'error': str(exc)}

        await websocket.send(json.dumps(result, ensure_ascii=False))


async def main_async(host: str, port: int, shared_token: str | None):
    async with websockets.serve(
        lambda ws: handle_client(ws, shared_token),
        host,
        port,
    ):
        await asyncio.Future()


def main():
    parser = argparse.ArgumentParser(description='WebSocket controlled shell endpoint')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=9002)
    parser.add_argument('--token', default='')
    args = parser.parse_args()

    token = (args.token or '').strip() or None
    asyncio.run(main_async(args.host, args.port, token))


if __name__ == '__main__':
    main()
