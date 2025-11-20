import os
import subprocess
import tempfile
import shutil
import base64
import json

TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJwcmluY2lwYWwiOiJzZXJ2aWNlYWNjb3VudC9zYS00YTU5ZTFkZS1jZDFlLTRhNDEtOWExMS1hZjNhM2NhZWQxMGIiLCJwcm9qZWN0SWQiOiJwLWQwY2RlYWI0In0.sy7d5iay37YdPaS0Lehhf23VllVALzkU8-ClcDXNTDy0ozKWdgGocRjdohNylrrEFK9QKAWntIOBsx5gJVaPNmUI9st_Ijd8jiIdpvRSdGv9kDteGTqOWo-D61pcczzLe21x5fGOXr43m9AKZk1J4qYDGZxknTdavpkmH-C7ALtQgFpQhr7rgBWvRTz85U48eIVsAuI0aC9kubWPyRisLKKr10rvXA0g7rkbRg4dwB2xQY6qBH2w4gVLKoMb7pSwS_tl1zE0Cp4w5wgAgdxQl__nFMljH8WGhgLdQtOMux42EbPLrjriInnfVZBPYb2owkpMQdNXa5CHB5-gojB49Q"

def create_dummy_project():
    tmp_dir = tempfile.mkdtemp(prefix='cerebrium_save_auth_')
    # create minimal main.py
    with open(os.path.join(tmp_dir, 'main.py'), 'w') as f:
        f.write("print('Hello World')\n")
    # create cerebrium.toml
    toml_content = """[cerebrium.deployment]
name = "cloud-terminal-test-auth"
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
"""
    with open(os.path.join(tmp_dir, 'cerebrium.toml'), 'w') as f:
        f.write(toml_content)
    return tmp_dir

def run_test_with_home_isolation(cwd, token):
    # Set HOME to cwd so .cerebrium config is created there
    env = os.environ.copy()
    env['HOME'] = cwd
    env['PYTHONUNBUFFERED'] = '1'
    # Ensure NO other auth env vars interfere
    for k in ['CEREBRIUM_SERVICE_ACCOUNT_TOKEN', 'CEREBRIUM_API_KEY', 'CEREBRIUM_TOKEN']:
        if k in env:
            del env[k]

    print(f"1. Saving auth config to {cwd}/.cerebrium/config ...")
    res = subprocess.run(
        ['cerebrium', 'save-auth-config', token],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True
    )
    print("STDOUT:", res.stdout)
    print("STDERR:", res.stderr)
    if res.returncode != 0:
        print("Save auth failed!")
        return

    print("2. Running deploy ...")
    res = subprocess.run(
        ['cerebrium', 'deploy', '-y'],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True
    )
    print("STDOUT:", res.stdout)
    print("STDERR:", res.stderr)
    print("Return Code:", res.returncode)

tmp_dir = create_dummy_project()
try:
    run_test_with_home_isolation(tmp_dir, TOKEN)
finally:
    shutil.rmtree(tmp_dir)
