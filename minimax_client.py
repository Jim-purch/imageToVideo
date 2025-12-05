import requests
import json
import os

class MinimaxClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.t2a_url = "https://api.minimax.io/v1/t2a_v2"
        self.get_voice_url = "https://api.minimax.io/v1/get_voice"

    def fetch_voices(self):
        """
        Fetches the list of available voices from Minimax API.
        Filters for system voices that are English.

        Returns:
            list: A list of dicts with 'voice_id' and 'voice_name'.
        """
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        # We request all, but then filter. Or we can request just system.
        # Docs say voice_type: system is valid.
        payload = {
            "voice_type": "system"
        }

        try:
            response = requests.post(self.get_voice_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()

            if 'base_resp' in data and data['base_resp'].get('status_code') != 0:
                 raise Exception(f"API Error ({data['base_resp'].get('status_code')}): {data['base_resp'].get('status_msg')}")

            voices = []
            # Only process system_voice as per requirement
            if 'system_voice' in data:
                for item in data['system_voice']:
                    voice_id = item.get('voice_id', '')
                    voice_name = item.get('voice_name', voice_id)

                    # Filter for English voices
                    # Usually English voices start with "English" or have it in the ID.
                    if voice_id.lower().startswith('english'):
                        voices.append({'voice_id': voice_id, 'voice_name': voice_name})

            return voices

        except requests.exceptions.RequestException as e:
            if e.response is not None:
                raise Exception(f"API Error ({e.response.status_code}): {e.response.text}")
            raise Exception(f"Network Error: {str(e)}")
        except Exception as e:
             raise Exception(f"Error fetching voices: {str(e)}")

    def generate_speech(self, text, output_file, voice_id="English_ManWithDeepVoice", speed=1.0, vol=1.0, pitch=0.0, tone="happy"):
        """
        Calls Minimax API to generate speech.

        Args:
            text (str): Text to convert to speech.
            output_file (str): Path to save the MP3 file.
            voice_id (str): Voice ID.
            speed (float): Speed.
            vol (float): Volume.
            pitch (float): Pitch (converted to int for API).
            tone (str): Emotion/Tone.

        Returns:
            bool: True if successful, raises Exception otherwise.
        """

        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        # Ensure pitch is integer as per API requirements/error logs
        try:
            pitch_int = int(pitch)
        except:
            pitch_int = 0

        payload = {
            "model": "speech-2.6-hd",
            "text": text,
            "stream": False,
            "language_boost": "auto",
            "output_format": "hex",
            "voice_setting": {
                "voice_id": voice_id,
                "speed": float(speed),
                "vol": float(vol),
                "pitch": pitch_int
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
            response = requests.post(self.t2a_url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()

            data = response.json()

            # Check for API-level error in base_resp
            if 'base_resp' in data and data['base_resp'].get('status_code') != 0:
                 raise Exception(f"API Error ({data['base_resp'].get('status_code')}): {data['base_resp'].get('status_msg')}")

            if 'data' in data and 'audio' in data['data']:
                hex_audio = data['data']['audio']
                audio_bytes = bytes.fromhex(hex_audio)
                with open(output_file, 'wb') as f:
                    f.write(audio_bytes)
                return True
            else:
                 # If we reached here without raising an error from base_resp, but still no audio data?
                 debug_info = json.dumps(data, indent=2)
                 raise Exception(f"Unexpected response format: {data.keys()} - {debug_info}")

        except requests.exceptions.RequestException as e:
            if e.response is not None:
                raise Exception(f"API Error ({e.response.status_code}): {e.response.text}")
            raise Exception(f"Network Error: {str(e)}")
        except Exception as e:
            raise Exception(f"Error processing audio: {str(e)}")
