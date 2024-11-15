# Import the necessary libraries
import warnings
import whisper
import tempfile

# suppress FutureWarning from torch.load
warnings.filterwarnings('ignore', category=FutureWarning)

model = None

def preload():
    global model
    model = whisper.load_model("base")
    return model

def transcribe(audio_bytes):
    global model
    if model is None:
        model = preload()

    #create temp audio file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as audio_file:
        audio_file.write(audio_bytes)

    # Transcribe the audio file
    result = model.transcribe(audio_file.name, fp16=False)