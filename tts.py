from gradio_client import Client
import os
import pygame.mixer

client = Client("innoai/Edge-TTS-Text-to-Speech")
pygame.mixer.init()
lang = "en-US-AndrewMultilingualNeural"

class TTS:
    def __init__(self, lang):
        if (lang.lower() == 'fr'):
            lang == "fr-FR-RemyMultilingualNeural"
        elif (lang.lower() == 'es'):
            lang == "es-ES-AlvaroNeural"
        elif (lang.lower() == 'de'):
            lang == "de-DE-FlorianMultilingualNeural"
        else:
            lang == "en-US-AndrewMultilingualNeural"

    def speech(self, text):
        speech = client.predict(
            text=text,
            voice=lang,
            rate=20,
            pitch=0,
            api_name="/predict"
        )
        pygame.mixer.music.load(speech[0])   # chargement de la musique
        pygame.mixer.music.play()   # la musique est jouée
        