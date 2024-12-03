from python.helpers import runtime, whisper

print("Running preload...")
runtime.initialize()

# preload transcription model
whisper.preload()