from gradio_client import Client
import os
from dotenv import load_dotenv
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame.mixer

load_dotenv()  # take environment variables from.env.
client = Client("innoai/Edge-TTS-Text-to-Speech")
pygame.mixer.init()

def speech(text):
    speech = client.predict(
        text=text,
        voice=os.getenv('EDGE_TTS_MODEL'),
        rate=20,
        pitch=0,
        api_name="/predict"
    )
    pygame.mixer.music.load(speech[0])   # chargement de la musique
    pygame.mixer.music.play()   # la musique est jouée
        