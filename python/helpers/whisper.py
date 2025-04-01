import base64
import warnings
import whisper
import tempfile
import asyncio
from python.helpers import runtime, rfc, settings
from python.helpers.print_style import PrintStyle

# Suppress FutureWarning from torch.load
warnings.filterwarnings("ignore", category=FutureWarning)

_model = None
_model_name = ""
is_updating_model = False  # Tracks whether the model is currently updating

async def preload(model_name:str):
    try:
        return await runtime.call_development_function(_preload, model_name)
    except Exception as e:
        if not runtime.is_development():
            raise e
        
async def _preload(model_name:str):
    global _model, _model_name, is_updating_model

    while is_updating_model:
        await asyncio.sleep(0.1)

    try:
        is_updating_model = True
        if not _model or _model_name != model_name:
                PrintStyle.standard(f"Loading Whisper model: {model_name}")
                _model = whisper.load_model(name=model_name) # type: ignore
                _model_name = model_name
    finally:
        is_updating_model = False

async def is_downloading():
    return await runtime.call_development_function(_is_downloading)

def _is_downloading():
    return is_updating_model

async def transcribe(model_name:str, audio_bytes_b64: str):
    return await runtime.call_development_function(_transcribe, model_name, audio_bytes_b64)


async def _transcribe(model_name:str, audio_bytes_b64: str):
    await _preload(model_name)
    
    # Decode audio bytes if encoded as a base64 string
    audio_bytes = base64.b64decode(audio_bytes_b64)

    # Create temp audio file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as audio_file:
        audio_file.write(audio_bytes)

    # Transcribe the audio file
    result = _model.transcribe(audio_file.name, fp16=False) # type: ignore
    return result
