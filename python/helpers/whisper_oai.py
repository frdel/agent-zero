# Import the necessary libraries
import whisper
import files

# Load the base model from Whisper
model = whisper.load_model("base")

# Add your Audio File
audio = files.get_abs_path("audio.ogg")

# Transcribe the audio file
result = model.transcribe(audio, fp16=False)
print(result["text"])