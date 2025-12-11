cd /gemini/code/index-tts
nohup /root/miniconda3/bin/python webui.py --port 7860 --host 0.0.0.0 > /tmp/webui.log 2>&1 &
echo "Started webui"
