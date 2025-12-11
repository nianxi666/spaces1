from gradio_client import Client, handle_file
import shutil
import requests

def test_remote_api():
    print("Initializing Client...")
    client = Client("http://direct.virtaicloud.com:21564")

    print("\nAPI Information:")
    client.view_api()

    # Download the test audio
    print("\nDownloading test audio...")
    audio_url = "https://s3.tebi.io/driver/admin/xiong2.mp3"
    local_audio = "test_audio.mp3"
    with requests.get(audio_url, stream=True) as r:
        with open(local_audio, 'wb') as f:
            shutil.copyfileobj(r.raw, f)

    print("Test audio downloaded.")

    # Prepare inputs matching the JS implementation
    prompt_text = "Same as the voice reference"
    text_to_synthesize = "This is a test synthesis from the python client."

    print("\nSending prediction request...")
    try:
        # Note: The signature here must match what we saw or what we expect.
        # Based on previous context, I'll try to match the JS structure.
        result = client.predict(
            prompt_text,                 # prompt
            handle_file(local_audio),    # audio_files
            text_to_synthesize,          # text
            handle_file(local_audio),    # audio_files_1
            0.8,                         # emo_weight
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, # vec1-8
            "",                          # emo_text
            False,                       # emo_random
            120,                         # max_text_tokens_per_segment
            True,                        # param_16 (do_sample)
            0.8,                         # param_17 (top_p)
            30,                          # param_18 (top_k)
            0.8,                         # param_19 (temperature)
            0.0,                         # param_20 (length_penalty)
            3,                           # param_21 (num_beams)
            10.0,                        # param_22 (repetition_penalty)
            1500,                        # param_23 (max_mel_tokens)
            api_name="/generate"
        )
        print("\nPrediction Successful!")
        print(f"Result: {result}")
        return True
    except Exception as e:
        print(f"\nPrediction Failed: {e}")
        return False

if __name__ == "__main__":
    test_remote_api()
