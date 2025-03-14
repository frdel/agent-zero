#!/usr/bin/env python3

import argparse
import os
import sys
import subprocess
import time
from datetime import datetime

# First ensure PIL is installed for the fallback
try:
    from PIL import Image
except ImportError:
    print("🔄 Installing PIL...")
    os.system("pip install Pillow")
    from PIL import Image

def ensure_dependencies():
    """Ensure all dependencies are installed - completely self-contained"""
    print("🔄 Checking and installing dependencies...")
    
    # First check if PyTorch is already installed and working
    try:
        import torch
        print(f"✅ Found PyTorch {torch.__version__}")
        if torch.cuda.is_available():
            print(f"✅ CUDA is available: {torch.cuda.get_device_name(0)}")
        else:
            print("⚠️ PyTorch found but CUDA is not available. Reinstalling with CUDA support...")
            # Force reinstall with CUDA
            os.system("pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121 --force-reinstall")
            # Reload torch
            import importlib
            if 'torch' in sys.modules:
                del sys.modules['torch']
            import torch
            print(f"✅ Reinstalled PyTorch {torch.__version__}")
    except (ImportError, ModuleNotFoundError):
        # Install PyTorch with CUDA support
        print("🔄 PyTorch not found. Installing with CUDA support...")
        os.system("pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121")
        # Reload torch
        import torch
        print(f"✅ Installed PyTorch {torch.__version__}")

    # Check and install diffusers and dependencies
    try:
        import diffusers
        print(f"✅ Found diffusers {diffusers.__version__}")
    except (ImportError, ModuleNotFoundError):
        print("🔄 Installing diffusers, transformers, and accelerate...")
        os.system("pip install diffusers transformers accelerate")
        # Reload modules
        import diffusers
        print(f"✅ Installed diffusers {diffusers.__version__}")
    
    return True

def generate_image(prompt, output_dir="/root/generated_images", seed=None):
    """Generate an image using Stable Diffusion"""
    # Always check dependencies first - completely self-contained
    ensure_dependencies()
    
    try:
        # Import required modules (they should be installed now)
        import torch
        from diffusers import StableDiffusionPipeline
                
        # Set device
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"🖥️ Using device: {device}")
        
        # Set seed if provided
        if seed is not None:
            torch.manual_seed(seed)
            print(f"🎲 Using seed: {seed}")
        
        print(f"🔄 Loading model...")
        print(f"🖼️ Generating image with prompt: \"{prompt}\"")
        start_time = time.time()
        
        # Create model
        pipe = StableDiffusionPipeline.from_pretrained(
            "runwayml/stable-diffusion-v1-5",  # Use v1-5 model for reliability
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            safety_checker=None  # Disable safety checker for speed
        )
        
        # Move to device and optimize
        pipe = pipe.to(device)
        pipe.enable_attention_slicing()
        
        print(f"✅ Model loaded in {time.time() - start_time:.2f} seconds")
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate the image
        gen_start_time = time.time()
        image = pipe(prompt=prompt, num_inference_steps=30).images[0]
        
        # Generate a filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"image_{timestamp}.png"
        filepath = os.path.join(output_dir, filename)
        
        # Save the image
        image.save(filepath)
        
        print(f"✅ Image generated in {time.time() - gen_start_time:.2f} seconds")
        print(f"💾 Image saved to: {filepath}")
        return True
    
    except Exception as e:
        print(f"❌ Error during image generation: {e}")
        # Create a fallback image
        generate_fallback_image(prompt, output_dir)
        return False

def generate_fallback_image(prompt, output_dir="/root/generated_images"):
    """Generate a simple black image as fallback"""
    print("⚠️ Using fallback to generate a basic image")
    
    try:
        # Create a black square image
        img = Image.new('RGB', (512, 512), color='black')
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate a filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"fallback_image_{timestamp}.png"
        filepath = os.path.join(output_dir, filename)
        
        # Save the image
        img.save(filepath)
        
        print(f"✅ Fallback image created with prompt: \"{prompt}\"")
        print(f"💾 Image saved to: {filepath}")
        return True
    except Exception as e:
        print(f"❌ Error during fallback image generation: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Generate images using Stable Diffusion")
    parser.add_argument("prompt", nargs="?", type=str, help="The prompt for image generation")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    args = parser.parse_args()
    
    # Handle case with no prompt
    if not args.prompt:
        print("❌ No prompt provided. Please specify a prompt.")
        print("Example: python image_generation.py 'A majestic dragon'")
        return 1
    
    # Generate the image (no need for separate install command)
    generate_image(args.prompt, seed=args.seed)
    return 0

if __name__ == "__main__":
    sys.exit(main())
