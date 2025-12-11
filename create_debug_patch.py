import os

patch = """
try:
    with open('webui.py', 'r', encoding='utf-8') as f:
        code = f.read()
except:
    with open('webui.py', 'r', encoding='latin-1') as f:
        code = f.read()

debug_code = '''
if not os.path.exists(cmd_args.model_dir):
    print(f"Model directory {cmd_args.model_dir} does not exist.")
    sys.exit(1)

print(f"Checking model dir: {cmd_args.model_dir}")
print(f"Files in model dir: {os.listdir(cmd_args.model_dir)}")
'''

# Insert debug before file check
if "for file in [" in code:
    code = code.replace("for file in [", debug_code + "\\nfor file in [")

with open('webui.py', 'w', encoding='utf-8') as f:
    f.write(code)
print("Added debug info")
"""

with open('add_debug.py', 'w') as f:
    f.write(patch)
print("Created add_debug.py")
