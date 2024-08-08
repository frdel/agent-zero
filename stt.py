import os, sys
from dotenv import load_dotenv
from groq import Groq
import pyaudio
import wave
from pynput.keyboard import Key, Controller
import numpy as np
from python.helpers.print_style import PrintStyle

load_dotenv()  # take environment variables from.env.

# Utility function to get API keys from environment variables
def get_api_key(service):
    return os.getenv(f"API_KEY_{service.upper()}") or os.getenv(f"{service.upper()}_API_KEY")

def record():
    client = Groq(
        api_key=get_api_key("groq")
    )

    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 2
    RATE = 44100
    WAVE_OUTPUT_FILENAME = "tmp_stt.wav"

    p = pyaudio.PyAudio()

    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    PrintStyle(background_color="red", font_color="white", bold=True, padding=True).print("Recording")

    frames = []
    silence_duration = 0
    silence_threshold = 0.5  # seuil de silence (en secondes)
    max_silence_duration = 3  # durée maximale de silence (en secondes)

    while True:
        data = stream.read(CHUNK)
        frames.append(data)

        # Analyse du signal audio pour détecter le silence
        audio_data = np.frombuffer(data, dtype=np.int16)
        audio_level = np.mean(np.abs(audio_data))
        if audio_level < 100:  # seuil de détection de silence (à ajuster)
            silence_duration += CHUNK / RATE
            if silence_duration > max_silence_duration:
                break
        else:
            silence_duration = 0

    PrintStyle(background_color="Yellow", font_color="black", bold=True, padding=True).print("Translation")

    stream.stop_stream()
    stream.close()
    p.terminate()

    filename = os.path.dirname(__file__) + "/tmp/" + WAVE_OUTPUT_FILENAME

    wf = wave.open(filename, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()

    with open(filename, "rb") as file:
        transcription = client.audio.transcriptions.create(
            file=(filename, file.read()),
            model="whisper-large-v3",
            prompt="Human talking to personnal ia agent",  # Optional
            response_format="json",  # Optional
            language="fr",  # Optional
            temperature=0.0  # Optional
        )
        keyboard = Controller()
        PrintStyle(background_color="green", font_color="white", bold=True, padding=True).print("Done")
        keyboard.type(transcription.text)
        keyboard.press(Key.enter)