import requests
import json
import os

class MinimaxClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.api_url = "https://api.minimax.io/v1/t2a_v2"

    def generate_speech(self, text, output_file, voice_id="English_ManWithDeepVoice", speed=1.0, vol=1.0, pitch=0.0, tone="happy"):
        """
        Calls Minimax API to generate speech.

        Args:
            text (str): Text to convert to speech.
            output_file (str): Path to save the MP3 file.
            voice_id (str): Voice ID.
            speed (float): Speed.
            vol (float): Volume.
            pitch (float): Pitch.
            tone (str): Emotion/Tone.

        Returns:
            bool: True if successful, raises Exception otherwise.
        """

        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        payload = {
            "model": "speech-2.6-hd",
            "text": text,
            "stream": False,
            "language_boost": "auto",
            "output_format": "hex",
            "voice_setting": {
                "voice_id": voice_id,
                "speed": speed,
                "vol": vol,
                "pitch": pitch
            },
            "pronunciation_dict": {
                "tone": [tone]
            },
            "audio_setting": {
                "sample_rate": 32000,
                "bitrate": 128000,
                "format": "mp3",
                "channel": 1
            },
            "voice_modify": {
                "pitch": 0,
                "intensity": 0,
                "timbre": 0,
                "sound_effects": "spacious_echo"
            }
        }

        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()

            data = response.json()

            # According to Minimax docs, "data" field contains the hex string if output_format is hex?
            # Or the body itself? The snippet says "output_format": "hex".
            # Usually, APIs return { "base_resp": { ... }, "data": { "audio": "HEX_STRING", ... } } or similar.
            # However, looking at standard Minimax T2A responses:
            # { "trace_id": "...", "data": { "audio": "hex string", "status": 1, ... } }
            # Let's assume data['data']['audio'] contains the hex string.

            if 'data' in data and 'audio' in data['data']:
                hex_audio = data['data']['audio']
                audio_bytes = bytes.fromhex(hex_audio)
                with open(output_file, 'wb') as f:
                    f.write(audio_bytes)
                return True
            else:
                 # Fallback/Debug: Print keys to see what we got
                 raise Exception(f"Unexpected response format: {data.keys()} - {data.get('base_resp', '')}")

        except requests.exceptions.RequestException as e:
            if e.response is not None:
                raise Exception(f"API Error ({e.response.status_code}): {e.response.text}")
            raise Exception(f"Network Error: {str(e)}")
        except Exception as e:
            raise Exception(f"Error processing audio: {str(e)}")
