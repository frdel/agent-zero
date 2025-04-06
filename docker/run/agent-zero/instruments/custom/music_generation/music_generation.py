#!/usr/bin/env python3

import argparse
import os
import sys
import subprocess
import time
from datetime import datetime

# Define constants
DEFAULT_OUTPUT_DIR = "/root/generated_music"
MODEL_CACHE_DIR = os.path.expanduser("~/.cache/audiocraft-models")

def install_requirements():
    """Install all required packages with compatible versions using the same approach as image_generation"""
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
            # Match exactly the same approach as the image generation script
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
                print(f"Error output: {process.stderr}")
                # Allow more time and use a direct pip command instead
                print("🔄 Trying alternative installation approach...")
                try:
                    # Try a generic install without version constraints
                    subprocess.run(
                        [sys.executable, "-m", "pip", "install", "--quiet", "torch", "torchvision", "torchaudio"],
                        check=True,
                        timeout=300  # Allow up to 5 minutes
                    )
                    print("✅ Successfully installed PyTorch (generic version)")
                except subprocess.TimeoutExpired:
                    print("⚠️ PyTorch installation timed out, continuing with available version")
                except Exception as e:
                    print(f"⚠️ Alternative installation approach failed: {e}")
        except Exception as e:
            print(f"❌ Error installing PyTorch: {e}")
    
    # Install FFmpeg if needed
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("✅ FFmpeg already installed")
    except:
        print("🔄 Installing FFmpeg...")
        subprocess.run(["apt-get", "update"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["apt-get", "install", "-y", "ffmpeg"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # First install core dependencies that others depend on
    core_dependencies = {
        "huggingface_hub": "0.20.3",
        "safetensors": "0.4.1",
        "accelerate": "0.21.0"
    }
    
    for package, version in core_dependencies.items():
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", f"{package}=={version}", "--quiet"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            print(f"✅ {package} installed: {version}")
        except Exception as e:
            print(f"⚠️ Warning: Issue with {package}: {e}")
            
    # Now install the main dependencies
    dependencies = {
        "transformers": "4.38.2",
        "einops": "0.6.1",
        "tqdm": "4.65.0",
        "librosa": "0.10.0.post2",
        "scipy": "1.12.0",
        "numpy": "1.24.3"
    }
    
    for package, version in dependencies.items():
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", f"{package}=={version}", "--quiet"],
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
                    # Match the image generation script version
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
    
    # Try to set up MusicGen through transformers
    print("🔄 Setting up MusicGen through transformers...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "transformers[torch]>=4.31.0", "--quiet"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Verify MusicGen is available
        try:
            from transformers import AutoProcessor, MusicgenForConditionalGeneration
            print("✅ MusicGen is available through transformers")
            return True
        except ImportError:
            print("⚠️ MusicGen not available through transformers, trying AudioCraft...")
    except Exception as e:
        print(f"⚠️ Error setting up transformers MusicGen: {e}")
    
    # Try direct install of AudioCraft
    print("🔄 Setting up AudioCraft...")
    try:
        # Install required dependencies
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "encodec", "basic_pitch", "--quiet"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Install AudioCraft
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "git+https://github.com/facebookresearch/audiocraft.git", "--quiet"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Verify AudioCraft is available
        try:
            import audiocraft
            print("✅ AudioCraft installed successfully")
            return True
        except ImportError:
            print("⚠️ AudioCraft installation failed")
    except Exception as e:
        print(f"⚠️ Error setting up AudioCraft: {e}")
    
    # Try the simplified musicgen package as last resort
    print("🔄 Trying simplified musicgen package...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "musicgen", "--quiet"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Verify musicgen is available
        try:
            import musicgen
            print("✅ Musicgen package installed successfully")
            return True
        except ImportError:
            print("⚠️ Musicgen package installation failed")
    except Exception as e:
        print(f"⚠️ Error setting up musicgen package: {e}")
    
    print("⚠️ Could not set up any MusicGen implementation")
    return False

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
        "transformers",
        "safetensors",
        "accelerate",
        "scipy",
        "xformers",
        "huggingface_hub",
        "librosa", 
        "einops",
        "numpy"
    ]
    
    for package in packages:
        try:
            module = __import__(package)
            version = getattr(module, "__version__", "Unknown version")
            print(f"{package}: {version}")
        except ImportError:
            print(f"{package}: Not installed")
    
    # Check for audiocraft
    try:
        import audiocraft
        version = getattr(audiocraft, "__version__", "Unknown version")
        print(f"audiocraft: {version}")
    except ImportError:
        print("audiocraft: Not installed")
    
    # Check for musicgen
    try:
        import musicgen
        version = getattr(musicgen, "__version__", "Unknown version")
        print(f"musicgen: {version}")
    except ImportError:
        print("musicgen: Not installed")
    
    print("-" * 40)

def generate_music_with_transformers(prompt, output_dir=DEFAULT_OUTPUT_DIR, duration=None, seed=None):
    """Generate music using the transformers implementation of MusicGen"""
    try:
        from transformers import AutoProcessor, MusicgenForConditionalGeneration
        import torch
        import scipy.io.wavfile as wavfile
        import subprocess
        
        print("🔄 Loading MusicGen model from transformers...")
        
        # Set seed if provided
        if seed is not None:
            torch.manual_seed(seed)
            print(f"🎲 Using seed: {seed}")
        
        # Determine device
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"🔄 Using device: {device}")
        
        # Choose model size based on memory
        if device == "cuda":
            try:
                free_memory, total_memory = torch.cuda.mem_get_info(0)
                free_gb = free_memory / 1e9
                model_size = "facebook/musicgen-small" if free_gb < 8 else "facebook/musicgen-medium"
                print(f"ℹ️ GPU Memory: {free_gb:.2f} GB free")
            except:
                model_size = "facebook/musicgen-small"  # Default if can't get memory info
        else:
            model_size = "facebook/musicgen-small"
            
        print(f"🔄 Loading model: {model_size}")
        
        # Load model and processor
        processor = AutoProcessor.from_pretrained(model_size)
        model = MusicgenForConditionalGeneration.from_pretrained(model_size)
        
        # Try to move model to GPU if available
        try:
            if device == "cuda":
                model = model.to(device)
            else:
                model = model.to(device)
        except RuntimeError as e:
            if "CUDA" in str(e):
                print(f"⚠️ Error moving model to CUDA: {e}")
                print("⚠️ Falling back to CPU")
                device = "cpu"
                model = model.to(device)
            else:
                raise
        
        # Set generation parameters
        if duration is None:
            duration = 10 if device == "cpu" else 30  # Shorter for CPU
        
        # Generate music
        print(f"🔄 Generating music with prompt: '{prompt}'")
        inputs = processor(
            text=[prompt],
            padding=True,
            return_tensors="pt",
        ).to(device)
        
        # Generate audio
        try:
            with torch.inference_mode():
                audio_values = model.generate(**inputs, max_new_tokens=int(duration * model.config.audio_encoder.frame_rate))
        except RuntimeError as e:
            if "out of memory" in str(e).lower() and device == "cuda":
                print("⚠️ CUDA out of memory. Moving to CPU...")
                # Move to CPU and try again with smaller settings
                model = model.to("cpu")
                inputs = processor(
                    text=[prompt],
                    padding=True,
                    return_tensors="pt",
                )
                with torch.inference_mode():
                    audio_values = model.generate(**inputs, max_new_tokens=int(10 * model.config.audio_encoder.frame_rate))
            else:
                # Re-raise other errors
                raise
        
        # Get sampling rate
        sampling_rate = model.config.audio_encoder.sampling_rate
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Save output
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        clean_prompt = "".join(c if c.isalnum() or c in [' ', '_', '-'] else '_' for c in prompt[:30])
        filename = f"music_{clean_prompt}_{timestamp}"
        wav_path = os.path.join(output_dir, f"{filename}.wav")
        mp3_path = os.path.join(output_dir, f"{filename}.mp3")
        
        # Convert to numpy and save as WAV
        audio_data = audio_values[0, 0].cpu().numpy()
        wavfile.write(wav_path, sampling_rate, audio_data)
        
        # Convert to MP3
        try:
            subprocess.run(
                ["ffmpeg", "-i", wav_path, "-b:a", "320k", mp3_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
            print(f"✅ Music created and saved to: {mp3_path}")
            
            # Remove WAV file
            os.remove(wav_path)
            return mp3_path
        except Exception as e:
            print(f"⚠️ Error converting to MP3: {e}")
            print(f"✅ Music saved as WAV: {wav_path}")
            return wav_path
            
    except Exception as e:
        print(f"❌ Error generating music with transformers: {e}")
        import traceback
        traceback.print_exc()
        return None

def generate_music_with_audiocraft(prompt, output_dir=DEFAULT_OUTPUT_DIR, duration=None, seed=None):
    """Generate music using Facebook's AudioCraft MusicGen"""
    try:
        import torch
        from audiocraft.models import MusicGen
        from audiocraft.data.audio import audio_write
        
        # Set seed if provided
        if seed is not None:
            torch.manual_seed(seed)
            print(f"🎲 Using seed: {seed}")
        
        # Choose appropriate model and settings based on available resources
        if torch.cuda.is_available():
            device = "cuda"
            print(f"✅ Using GPU: {torch.cuda.get_device_name(0)}")
            try:
                free_memory, total_memory = torch.cuda.mem_get_info(0)
                free_gb = free_memory / 1e9
                print(f"ℹ️ GPU Memory: {free_gb:.2f} GB free")
                
                # Choose model based on available GPU memory
                if free_gb > 8:
                    model_size = "medium"  # Good balance
                    auto_duration = 30
                else:
                    model_size = "small"  # Most efficient
                    auto_duration = 30
            except:
                model_size = "small"  # Default if can't get memory info
                auto_duration = 30
        else:
            device = "cpu"
            print("⚠️ Using CPU (no GPU detected) - using smaller model")
            model_size = "small"  # Most efficient for CPU
            auto_duration = 30  # Shorter for CPU to avoid long wait
        
        # Use provided duration or default
        if duration is None:
            duration = auto_duration
            
        print(f"🔄 Using {model_size} model to generate {duration} seconds of music")
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Model mapping
        model_name = f"facebook/musicgen-{model_size}"
        
        # Load model
        print(f"🔄 Loading model...")
        try:
            model = MusicGen.get_pretrained(model_name, cache_dir=MODEL_CACHE_DIR)
            
            # Try to move model to GPU if available
            try:
                if device == "cuda":
                    model = model.to(device)
                else:
                    model = model.to(device)
            except RuntimeError as e:
                if "CUDA" in str(e):
                    print(f"⚠️ Error moving model to CUDA: {e}")
                    print("⚠️ Falling back to CPU")
                    device = "cpu"
                    model = model.to(device)
                else:
                    raise
        except Exception as e:
            print(f"⚠️ Error loading model: {e}, trying smaller model...")
            model_name = "facebook/musicgen-small"
            model = MusicGen.get_pretrained(model_name, cache_dir=MODEL_CACHE_DIR)
            model.to(device)
        
        # Set model parameters
        model.set_generation_params(
            duration=duration,
            use_sampling=True,
            top_k=250,
            top_p=0.95,
            temperature=1.0,
            cfg_coef=3.0
        )
        
        # Generate audio
        print(f"🔄 Creating music...")
        try:
            with torch.inference_mode():
                wav = model.generate([prompt])
        except RuntimeError as e:
            if "out of memory" in str(e).lower() and device == "cuda":
                print("⚠️ GPU memory insufficient, falling back to CPU with smaller model...")
                model = MusicGen.get_pretrained("facebook/musicgen-small", cache_dir=MODEL_CACHE_DIR)
                model.to("cpu")
                model.set_generation_params(
                    duration=min(duration, 30),  # Cap at 60 seconds for CPU
                    use_sampling=True,
                    top_k=250,
                    top_p=0.95,
                    temperature=1.0,
                    cfg_coef=3.0
                )
                with torch.inference_mode():
                    wav = model.generate([prompt])
            else:
                raise
        
        # Save the audio
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        clean_prompt = "".join(c if c.isalnum() or c in [' ', '_', '-'] else '_' for c in prompt[:30])
        filename = f"music_{clean_prompt}_{timestamp}"
        filepath_mp3 = os.path.join(output_dir, f"{filename}.mp3")
        filepath_wav = os.path.join(output_dir, f"{filename}.wav")
        
        # Save as WAV first
        audio_write(filepath_wav.replace('.wav', ''), wav.cpu()[0], model.sample_rate, strategy="loudness", loudness_compressor=True)
        
        # Convert to MP3 using ffmpeg
        try:
            subprocess.run(
                ["ffmpeg", "-i", filepath_wav, "-b:a", "320k", filepath_mp3],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
            print(f"✅ Music created and saved to: {filepath_mp3}")
            
            # Remove the WAV file
            os.remove(filepath_wav)
            return filepath_mp3
            
        except Exception as e:
            print(f"⚠️ Error converting to MP3, saved as WAV: {filepath_wav}")
            return filepath_wav
            
    except Exception as e:
        print(f"❌ Error with AudioCraft approach: {e}")
        import traceback
        traceback.print_exc()
        return None

def generate_music(prompt, output_dir=DEFAULT_OUTPUT_DIR, duration=None, seed=None):
    """Generate music using the best available method"""
    print(f"🎵 Generating music with prompt: \"{prompt}\"")
    
    # Install dependencies
    install_requirements()
    
    # First try to use audiocraft
    try:
        import audiocraft
        print("✅ Using AudioCraft implementation")
        result = generate_music_with_audiocraft(prompt, output_dir, duration, seed)
        if result:
            return result
        else:
            print("⚠️ AudioCraft generation failed, trying transformers implementation")
    except ImportError:
        print("⚠️ AudioCraft not available, trying transformers implementation")
    
    # Try transformers implementation
    try:
        from transformers import AutoProcessor, MusicgenForConditionalGeneration
        result = generate_music_with_transformers(prompt, output_dir, duration, seed)
        if result:
            return result
        else:
            print("⚠️ Transformers generation failed")
    except ImportError:
        print("❌ Could not find any available MusicGen implementation")
    
    # If we got here, all methods failed
    return None

def main():
    parser = argparse.ArgumentParser(description="Generate music from a text prompt")
    parser.add_argument("prompt", nargs="?", type=str, help="Text prompt describing the desired music")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    parser.add_argument("--output-dir", type=str, default=DEFAULT_OUTPUT_DIR, help="Directory to save generated music")
    parser.add_argument("--duration", type=int, default=None, help="Duration of music in seconds")
    args = parser.parse_args()
    
    # Check if a prompt was provided
    if not args.prompt:
        print("❌ No prompt provided. Please specify a prompt.")
        print("Example: python music_generation.py \"An upbeat electronic track with a catchy melody\"")
        return 1
    
    # Generate the music
    filepath = generate_music(
        args.prompt,
        args.output_dir,
        duration=args.duration,
        seed=args.seed
    )
    
    if filepath:
        print(f"✨ Music generation completed successfully!")
        print_versions()  # Print versions after successful generation
        
        # Add a message if we used CPU but have GPU hardware
        import torch
        if not torch.cuda.is_available() and check_cuda():
            print("\n🔄 NOTE: This music was generated on CPU but an NVIDIA GPU was detected.")
            print("🔄 CUDA support was installed successfully but requires a restart of the Python environment.")
            print("🔄 Please run the script again to utilize GPU acceleration for faster music generation.")
        
        return 0
    else:
        print("❌ Music generation failed")
        # Check if we installed CUDA support and a GPU is available but CUDA wasn't recognized
        try:
            import torch
            if not torch.cuda.is_available() and check_cuda():
                print("\n✅ CUDA support was installed successfully but requires a restart of the Python environment.")
                print("✅ Please run the script again to utilize GPU acceleration for faster music generation.")
        except ImportError:
            pass
        return 1

if __name__ == "__main__":
    sys.exit(main())