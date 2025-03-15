#!/usr/bin/env python3

import argparse
import os
import sys
import subprocess
import time
from datetime import datetime

# Define constants
DEFAULT_OUTPUT_DIR = "/root/generated_images"
MODEL_CACHE_DIR = os.path.expanduser("~/.cache/stable-diffusion")

def install_requirements():
    """Install all required packages with compatible versions"""
    print("🔄 Checking dependencies...")
    
    # First check what's already installed
    try:
        import torch
        print(f"✅ PyTorch already installed: {torch.__version__}")
        pytorch_installed = True
        
        # Check if CUDA is available in the installed version
        cuda_available = torch.cuda.is_available()
        if cuda_available:
            print(f"✅ CUDA already available: {torch.cuda.get_device_name(0)}")
        else:
            print("⚠️ PyTorch is installed but CUDA is not available")
            # If PyTorch is installed without CUDA, uninstall and reinstall with CUDA
            subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "torch", "torchvision", "torchaudio"])
            pytorch_installed = False
            
    except ImportError:
        print("❌ PyTorch not installed")
        pytorch_installed = False
        
    # Only install PyTorch if it's not already installed or was uninstalled due to missing CUDA
    if not pytorch_installed:
        print("🔄 Installing PyTorch with CUDA support...")
        try:
            process = subprocess.run(
                [sys.executable, "-m", "pip", "install", "torch==2.6.0+cu124", "torchvision", "torchaudio", "--index-url", "https://download.pytorch.org/whl/cu124"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            if process.returncode == 0:
                print("✅ Successfully installed PyTorch with CUDA support")
            else:
                print("⚠️ Failed to install PyTorch with CUDA, falling back to CPU version")
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "torch", "torchvision", "torchaudio"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
        except Exception as e:
            print(f"❌ Error installing PyTorch: {e}")
    
    # First install core dependencies that others depend on
    core_dependencies = {
        "huggingface_hub": "0.20.3",
        "safetensors": "0.4.1",
        "accelerate": "0.21.0"
    }
    
    for package, version in core_dependencies.items():
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "uninstall", "-y", package],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            print(f"🔄 Installing {package} version {version}")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", f"{package}=={version}", "--quiet"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            print(f"✅ {package} installed: {version}")
        except Exception as e:
            print(f"⚠️ Warning: Issue with {package}: {e}")
            
    # Now install the main dependencies
    dependencies = {
        "diffusers": "0.25.0",  # Updated to a version compatible with Python 3.12
        "transformers": "4.38.2",
        "scipy": "1.15.2"
    }
    
    for package, version in dependencies.items():
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "uninstall", "-y", package],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            print(f"🔄 Installing {package} version {version}")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", f"{package}=={version}", "--quiet"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            print(f"✅ {package} installed: {version}")
        except Exception as e:
            print(f"⚠️ Warning: Issue with {package}: {e}")
    
    # Try to install xformers if CUDA is available
    try:
        import torch
        if torch.cuda.is_available():
            try:
                import xformers
                print(f"✅ xformers already installed: {xformers.__version__}")
            except ImportError:
                print("🔄 Installing xformers for better GPU performance...")
                try:
                    subprocess.run(
                        [sys.executable, "-m", "pip", "install", "xformers==0.0.29.post3", "--quiet"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    )
                    print("✅ Successfully installed xformers")
                except Exception as e:
                    print(f"⚠️ Warning: Failed to install xformers: {e}")
                    print("⚠️ This is not critical, generation will work without it.")
    except Exception:
        pass
        
    print("✅ Dependency check complete")
    return True

def check_cuda():
    """Check if CUDA is available"""
    try:
        # Check if nvidia-smi command works
        nvidia_smi = subprocess.run(['nvidia-smi'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        if nvidia_smi.returncode == 0:
            print("✅ NVIDIA GPU detected via nvidia-smi")
            return True
            
        return False
    except:
        return False

def print_versions():
    """Print installed versions of all relevant packages"""
    print("\n📦 Installed Package Versions:")
    print("-" * 40)
    
    try:
        import torch
        print(f"PyTorch: {torch.__version__}")
        print(f"CUDA Available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"CUDA Version: {torch.version.cuda}")
            print(f"cuDNN Version: {torch.backends.cudnn.version() if torch.backends.cudnn.is_available() else 'Not available'}")
            print(f"GPU: {torch.cuda.get_device_name(0)}")
    except ImportError:
        print("PyTorch: Not installed")
    
    packages = [
        "diffusers",
        "transformers",
        "safetensors",
        "accelerate",
        "scipy",
        "xformers",
        "huggingface_hub"
    ]
    
    for package in packages:
        try:
            module = __import__(package)
            version = getattr(module, "__version__", "Unknown version")
            print(f"{package}: {version}")
        except ImportError:
            print(f"{package}: Not installed")
    
    print("-" * 40)

def generate_image(prompt, output_dir=DEFAULT_OUTPUT_DIR, seed=None, size=(512, 512)):
    """Generate an image using Stable Diffusion
    
    Args:
        prompt: Text prompt describing the image to generate
        output_dir: Directory to save the generated image
        seed: Random seed for reproducibility (optional)
        size: Output image size as (width, height) tuple (default: 512x512)
    """
    print(f"🖼️ Generating image with prompt: \"{prompt}\"")
    
    # Install dependencies
    install_requirements()
    
    # Import required libraries
    try:
        import torch
        from diffusers import StableDiffusionPipeline
        from PIL import Image
        
        print(f"✅ Using PyTorch {torch.__version__}")
        print(f"✅ CUDA available: {torch.cuda.is_available()}")
        
        if torch.cuda.is_available():
            device = "cuda"
            print(f"✅ Using CUDA device: {torch.cuda.get_device_name(0)}")
            print(f"ℹ️ GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
        else:
            device = "cpu"
            print("⚠️ Using CPU (CUDA not available)")
        
        # Set seed if provided
        if seed is not None:
            torch.manual_seed(seed)
            print(f"🎲 Using seed: {seed}")
        
        # Load the model
        print("🔄 Loading Stable Diffusion model...")
        start_time = time.time()
        
        try:
            # Load the model with appropriate settings
            pipe = StableDiffusionPipeline.from_pretrained(
                "runwayml/stable-diffusion-v1-5",
                torch_dtype=torch.float16 if device == "cuda" else torch.float32,
                safety_checker=None,
                cache_dir=MODEL_CACHE_DIR
            )
            
            # Move model to device
            pipe = pipe.to(device)
            
            # Enable memory optimizations
            pipe.enable_attention_slicing()
            
            # Enable xformers if available and on CUDA
            if device == "cuda":
                try:
                    import xformers
                    pipe.enable_xformers_memory_efficient_attention()
                    print("✅ Using xformers for memory efficient attention")
                except ImportError:
                    print("⚠️ xformers not available, using standard attention")
            
            print(f"✅ Model loaded in {time.time() - start_time:.2f} seconds")
            
            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate the image
            print(f"🔄 Generating image on {device}...")
            gen_start_time = time.time()
            
            # CUDA out of memory handling
            try:
                with torch.inference_mode():
                    output = pipe(
                        prompt=prompt,
                        num_inference_steps=30 if device == "cuda" else 20,
                        guidance_scale=7.5,
                        height=size[1],
                        width=size[0]
                    )
                    image = output.images[0]
                
                print(f"✅ Image generated in {time.time() - gen_start_time:.2f} seconds")
            except RuntimeError as e:
                if "out of memory" in str(e).lower() and device == "cuda":
                    print("⚠️ CUDA out of memory. Moving to CPU...")
                    # Move to CPU and try again with smaller settings
                    pipe = pipe.to("cpu")
                    with torch.inference_mode():
                        output = pipe(
                            prompt=prompt,
                            num_inference_steps=20,  # Fewer steps
                            guidance_scale=7.0,     # Lower guidance scale
                            height=min(512, size[1]),  # Limit size
                            width=min(512, size[0])
                        )
                        image = output.images[0]
                    print(f"✅ Image generated on CPU in {time.time() - gen_start_time:.2f} seconds")
                else:
                    # Re-raise other errors
                    raise
            
            # Save the image
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"image_{timestamp}.png"
            filepath = os.path.join(output_dir, filename)
            
            image.save(filepath)
            print(f"💾 Image saved to: {filepath}")
            
            return filepath
            
        except Exception as e:
            print(f"❌ Error generating image: {e}")
            return None
        
    except ImportError as e:
        print(f"❌ Error importing required modules: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Generate images using Stable Diffusion")
    parser.add_argument("prompt", nargs="?", type=str, help="The prompt for image generation")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    parser.add_argument("--output-dir", type=str, default=DEFAULT_OUTPUT_DIR, help="Directory to save generated images")
    parser.add_argument("--width", type=int, default=512, help="Width of the generated image (default: 512)")
    parser.add_argument("--height", type=int, default=512, help="Height of the generated image (default: 512)")
    args = parser.parse_args()
    
    # Check if a prompt was provided
    if not args.prompt:
        print("❌ No prompt provided. Please specify a prompt.")
        print("Example: python image_generation.py 'A majestic dragon'")
        return 1
    
    # Generate the image
    filepath = generate_image(
        args.prompt,
        args.output_dir,
        seed=args.seed,
        size=(args.width, args.height)
    )
    
    if filepath:
        print(f"✨ Image generation completed successfully!")
        print_versions()  # Print versions after successful generation
        return 0
    else:
        print("❌ Image generation failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
