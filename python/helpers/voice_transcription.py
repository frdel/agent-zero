import whisper
import io
import base64
import numpy as np
from typing import Optional, Union, BinaryIO
from whisper.audio import load_audio
import tempfile
import os
import subprocess
import warnings

# suppress FutureWarning from torch.load
warnings.filterwarnings('ignore', category=FutureWarning)

class VoiceTranscription:
  @staticmethod
  def load_model(model_size: str = "base"):
      """
      Load a Whisper model with the specified size.
      """
      try:
          return whisper.load_model(model_size)
      except Exception as e:
          print(f"Error loading Whisper model: {e}")
          return None

  @classmethod
  def transcribe_bytes(cls, audio_bytes: Union[str, bytes, BinaryIO], 
                       model_size: str = "base", 
                       language: Optional[str] = None) -> str:
      """
      Transcribe audio from bytes or a file-like object.
      """
      model = cls.load_model(model_size)
      if not model:
          raise RuntimeError("Could not load Whisper model")
    
      # Decode audio bytes if encoded as a base64 string
      if isinstance(audio_bytes, str):
          try:
              audio_bytes = base64.b64decode(audio_bytes)
          except Exception as e:
              print(f"Error decoding base64 audio data: {e}")
              raise
    
      # Save audio bytes to a temporary file with .webm extension
      with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp_input_file:
          tmp_input_file.write(audio_bytes)
          temp_input_path = tmp_input_file.name
    
      try:
          # Define the output path with .wav extension
          with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_output_file:
              temp_output_path = tmp_output_file.name

          # Convert WebM to WAV using FFmpeg
          ffmpeg_cmd = [
              'ffmpeg', '-y', '-i', temp_input_path,
              '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1',
              temp_output_path
          ]

          print(f"Running FFmpeg command: {' '.join(ffmpeg_cmd)}")

          # Run FFmpeg command using subprocess
          try:
            subprocess.run(
                ffmpeg_cmd, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, check=True  # Suppressed stderr
            )
          except subprocess.CalledProcessError as e:
            error_message = e.stderr.decode().strip()
            print(f"FFmpeg error: {error_message}")
    
          # Log the temporary file path for debugging
          print(f"Transcribing audio from temporary file: {temp_output_path}")
          
          # Load audio using Whisper's load_audio
          audio = load_audio(temp_output_path)
          
          # Transcribe using the Whisper model
          result = model.transcribe(audio, fp16=False, language=language)
          text = result.get("text", "").strip()
          
          # Log the transcription result
          print(f"Transcription result: {text}")
          
          return text
      
      except subprocess.CalledProcessError as e:
            error_message = e.stderr.decode().strip()
            print(f"FFmpeg error: {error_message}")
            # Return empty string or handle as appropriate
            return ""
      except Exception as transcribe_error:
            print(f"Transcription error: {transcribe_error}")
            # Return empty string or handle as appropriate
            return ""
      finally:
          
          # Clean up temporary files
          if os.path.exists(temp_input_path):
              os.remove(temp_input_path)
          if os.path.exists(temp_output_path):
              os.remove(temp_output_path)
