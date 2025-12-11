try:
    with open('remote_webui.py', 'r', encoding='utf-16') as f:
        content = f.read()
    with open('remote_webui_clean.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Success")
except Exception as e:
    print(f"Error: {e}")
