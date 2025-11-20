import os
import subprocess
import tempfile
import shutil
import base64
import json

# Real token from memory
TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJwcmluY2lwYWwiOiJzZXJ2aWNlYWNjb3VudC9zYS00YTU5ZTFkZS1jZDFlLTRhNDEtOWExMS1hZjNhM2NhZWQxMGIiLCJwcm9qZWN0SWQiOiJwLWQwY2RlYWI0In0.sy7d5iay37YdPaS0Lehhf23VllVALzkU8-ClcDXNTDy0ozKWdgGocRjdohNylrrEFK9QKAWntIOBsx5gJVaPNmUI9st_Ijd8jiIdpvRSdGv9kDteGTqOWo-D61pcczzLe21x5fGOXr43m9AKZk1J4qYDGZxknTdavpkmH-C7ALtQgFpQhr7rgBWvRTz85U48eIVsAuI0aC9kubWPyRisLKKr10rvXA0g7rkbRg4dwB2xQY6qBH2w4gVLKoMb7pSwS_tl1zE0Cp4w5wgAgdxQl__nFMljH8WGhgLdQtOMux42EbPLrjriInnfVZBPYb2owkpMQdNXa5CHB5-gojB49Q"

def decode_project_id(token_value):
    try:
        parts = token_value.split('.')
        if len(parts) < 2:
            return None
        payload_b64 = parts[1]
        pad = '=' * (-len(payload_b64) % 4)
        payload_data = base64.urlsafe_b64decode(payload_b64 + pad)
        payload_json = json.loads(payload_data.decode('utf-8'))
        return payload_json.get('projectId')
    except Exception:
        return None

PROJECT_ID = decode_project_id(TOKEN)
print(f"Project ID from token: {PROJECT_ID}")

def create_dummy_project():
    tmp_dir = tempfile.mkdtemp(prefix='cerebrium_test_')

    # create minimal main.py
    with open(os.path.join(tmp_dir, 'main.py'), 'w') as f:
        f.write("print('Hello World')\n")

    # create cerebrium.toml
    # Mimic what api.py does
    toml_content = """[cerebrium.deployment]
name = "cloud-terminal-test"
python_version = "3.12"
disable_auth = true
include = ["./*"]
exclude = [".git", "__pycache__", ".DS_Store"]

[cerebrium.hardware]
cpu = 2.0
memory = 2.0
provider = "aws"
region = "us-east-1"

[cerebrium.scaling]
min_replicas = 0
max_replicas = 1
cooldown = 30
replica_concurrency = 1
"""
    with open(os.path.join(tmp_dir, 'cerebrium.toml'), 'w') as f:
        f.write(toml_content)

    return tmp_dir

def run_deploy(cwd, token):
    env = os.environ.copy()
    env['CEREBRIUM_SERVICE_ACCOUNT_TOKEN'] = token
    env['PYTHONUNBUFFERED'] = '1'

    # Ensure we are NOT using cached credentials by setting a custom config dir?
    # Or just relying on precedence.

    print(f"Running deploy in {cwd}...")
    try:
        proc = subprocess.run(
            ['cerebrium', 'deploy', '-y'],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=60
        )
        print("STDOUT:", proc.stdout)
        print("STDERR:", proc.stderr)
        print("Return Code:", proc.returncode)
    except Exception as e:
        print(f"Execution failed: {e}")

tmp_dir = create_dummy_project()
try:
    run_deploy(tmp_dir, TOKEN)
finally:
    shutil.rmtree(tmp_dir)
