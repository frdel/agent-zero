from python.helpers.extension import Extension
from agent import Agent, LoopData
import os
import io
import base64
from PIL import Image

class IncludeAttachments(Extension):
    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        # Check if there are attachments in agent data
        attachments = self.agent.get_data('attachments') or []
        if attachments:
            loop_data.attachments = [] # Initialize attachments list for loop_data

            # For each attachment, compress and encode the image
            for attachment_path in attachments:
                if os.path.exists(attachment_path):
                    # Prepare the base64-encoded image
                    compressed_image_base64 = self.compress_and_encode_image(attachment_path)
                    if compressed_image_base64:
                        # Append the image data to loop_data.attachments
                        loop_data.attachments.append(f"<image>{compressed_image_base64}</image>")

            # Clear attachments from agent data
            self.agent.set_data('attachments', [])

    def compress_and_encode_image(self, image_path: str) -> str:
        try:
            # Open an image file
            with Image.open(image_path) as img:
                # Convert image to RGB if it's in RGBA mode
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                # Resize the image to a reasonable size
                max_dimension = 800  # You can adjust this value
                img.thumbnail((max_dimension, max_dimension))
                
                # Compress the image
                buffered = io.BytesIO()
                # Save as JPEG to ensure compression; you can adjust quality
                img.save(buffered, format="JPEG", quality=70, optimize=True)
                compressed_image = buffered.getvalue()
                
                # Encode the compressed image in base64
                return base64.b64encode(compressed_image).decode('utf-8')
        except Exception as e:
            print(f"Error compressing and encoding image {image_path}: {e}")
            return ""

    def estimate_token_count(self, message: str) -> int:
        # Simple estimation: assume 4 characters per token
        return len(message) // 4
