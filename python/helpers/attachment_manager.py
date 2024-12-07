import os
import io
import base64
from PIL import Image
from typing import Dict, List, Optional, Tuple
from werkzeug.utils import secure_filename

from python.helpers.print_style import PrintStyle

class AttachmentManager:
  ALLOWED_EXTENSIONS = {
      'image': {'jpg', 'jpeg', 'png', 'bmp'},
      'code': {'py', 'js', 'sh', 'html', 'css'},
      'document': {'md', 'pdf', 'txt', 'csv', 'json'}
  }
  
  def __init__(self, work_dir: str):
      self.work_dir = work_dir
      os.makedirs(work_dir, exist_ok=True)

  def is_allowed_file(self, filename: str) -> bool:
      ext = self.get_file_extension(filename)
      all_allowed = set().union(*self.ALLOWED_EXTENSIONS.values())
      return ext in all_allowed

  def get_file_type(self, filename: str) -> str:
      ext = self.get_file_extension(filename)
      for file_type, extensions in self.ALLOWED_EXTENSIONS.items():
          if ext in extensions:
              return file_type
      return 'unknown'

  @staticmethod
  def get_file_extension(filename: str) -> str:
      return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
  
  def validate_mime_type(self, file) -> bool:
      try:
          mime_type = file.content_type
          return mime_type.split('/')[0] in ['image', 'text', 'application']
      except AttributeError:
          return False

  def save_file(self, file, filename: str) -> Tuple[str, Dict]:
      """Save file and return path and metadata"""
      try:
          filename = secure_filename(filename)
          if not filename:
              raise ValueError("Invalid filename")
              
          file_path = os.path.join(self.work_dir, filename)
          
          file_type = self.get_file_type(filename)
          metadata = {
              'filename': filename,
              'type': file_type,
              'extension': self.get_file_extension(filename),
              'preview': None
          }
  
          # Save file
          file.save(file_path)
  
          # Generate preview for images
          if file_type == 'image':
              metadata['preview'] = self.generate_image_preview(file_path)
  
          return file_path, metadata
        
      except Exception as e:
          PrintStyle.error(f"Error saving file {filename}: {e}")
          return None, {} # type: ignore

  def generate_image_preview(self, image_path: str, max_size: int = 800) -> Optional[str]:
      try:
          with Image.open(image_path) as img:
              # Convert image if needed
              if img.mode in ('RGBA', 'P'):
                  img = img.convert('RGB')
              
              # Resize for preview
              img.thumbnail((max_size, max_size))
              
              # Save to buffer
              buffer = io.BytesIO()
              img.save(buffer, format="JPEG", quality=70, optimize=True)
              
              # Convert to base64
              return base64.b64encode(buffer.getvalue()).decode('utf-8')
      except Exception as e:
          PrintStyle.error(f"Error generating preview for {image_path}: {e}")
          return None
      