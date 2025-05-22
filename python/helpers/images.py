from PIL import Image
import io
import math


def compress_image(image_data: bytes, *, max_pixels: int = 256_000, quality: int = 50) -> bytes:
    """Compress an image by scaling it down and converting to JPEG with quality settings.
    
    Args:
        image_data: Raw image bytes
        max_pixels: Maximum number of pixels in the output image (width * height)
        quality: JPEG quality setting (1-100)
    
    Returns:
        Compressed image as bytes
    """
    # load image from bytes
    img = Image.open(io.BytesIO(image_data))
    
    # calculate scaling factor to get to max_pixels
    current_pixels = img.width * img.height
    if current_pixels > max_pixels:
        scale = math.sqrt(max_pixels / current_pixels)
        new_width = int(img.width * scale)
        new_height = int(img.height * scale)
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # convert to RGB if needed (for JPEG)
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    
    # save as JPEG with compression
    output = io.BytesIO()
    img.save(output, format='JPEG', quality=quality, optimize=True)
    return output.getvalue()
