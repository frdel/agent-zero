#!/usr/bin/env python3

import argparse
import os
import sys
import subprocess
import time
from datetime import datetime
import json
import tempfile
from pathlib import Path
import shutil
import threading
from tqdm import tqdm

# Define constants
DEFAULT_OUTPUT_DIR = "/root/generated_videos"
MODEL_CACHE_DIR = os.path.expanduser("~/.cache/video-models")
DEFAULT_DURATION = 5  # Default video duration in seconds
MAX_FRAMES = 24 * 30  # Maximum number of frames (30s at 24fps)
DEFAULT_FPS = 24

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
    
    # Install FFmpeg if needed
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("✅ FFmpeg already installed")
    except:
        print("🔄 Installing FFmpeg...")
        try:
            subprocess.run(["apt-get", "update"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(["apt-get", "install", "-y", "ffmpeg"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print("✅ FFmpeg installed")
        except Exception as e:
            print(f"❌ Error installing FFmpeg: {e}")
            return False
    
    # First install core dependencies that others depend on
    core_dependencies = {
        "huggingface_hub": "0.20.3",
        "safetensors": "0.4.1",
        "accelerate": "0.21.0",
        "transformers": "4.38.2"
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
    
    # Install video generation library dependencies
    video_dependencies = {
        "diffusers": "0.25.0",
        "einops": "0.7.0",
        "scipy": "1.12.0",
        "opencv-python": "4.8.1.78",
        "imageio": "2.33.1",
        "imageio-ffmpeg": "0.4.9",
        "Pillow": "10.1.0",
        "tqdm": "4.66.1"
    }
    
    for package, version in video_dependencies.items():
        try:
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
        "huggingface_hub",
        "einops",
        "opencv-python",
        "imageio",
        "imageio-ffmpeg",
        "Pillow",
        "tqdm"
    ]
    
    for package in packages:
        try:
            module = __import__(package.replace("-", "_"))
            version = getattr(module, "__version__", "Unknown version")
            print(f"{package}: {version}")
        except ImportError:
            print(f"{package}: Not installed")
    
    print("-" * 40)

def generate_video_frames(
    prompt,
    negative_prompt="poor quality, distorted, blurry, bad, ugly",
    width=512,
    height=512,
    num_frames=24,
    fps=24,
    seed=None,
    output_dir=None,
    temp_dir=None,
    quality_mode=False  # Add quality_mode parameter
):
    """Generate video frames using Stable Diffusion video model"""
    import torch
    from diffusers import DiffusionPipeline, DPMSolverMultistepScheduler
    from diffusers.utils import export_to_video
    import numpy as np
    
    # Use quality settings if available and quality_mode is enabled
    global QUALITY_SETTINGS
    if quality_mode and 'QUALITY_SETTINGS' in globals():
        print("💎 Applying optimized quality settings")
        
        # Apply quality settings to the generation parameters
        motion_bucket_id = QUALITY_SETTINGS.get("motion_bucket_id", 80)
        noise_aug_strength = QUALITY_SETTINGS.get("noise_aug_strength", 0.15)
        quality_steps = QUALITY_SETTINGS.get("num_inference_steps", 30)
        quality_decode_chunk = QUALITY_SETTINGS.get("decode_chunk_size", 1)
        quality_frames = QUALITY_SETTINGS.get("num_frames", 8)
        guidance_scale = QUALITY_SETTINGS.get("guidance_scale", 7.5)
        
        print(f"🔧 Using motion_bucket_id={motion_bucket_id}, noise_aug_strength={noise_aug_strength}")
        print(f"🔧 Generating {quality_frames} frames with {quality_steps} inference steps")
        
        # Override with quality settings
        num_frames = min(num_frames, quality_frames)
    else:
        # Default values if not in quality mode
        motion_bucket_id = 45
        noise_aug_strength = 0.1
        guidance_scale = 7.5  # For initial image generation
    
    print(f"🎬 Generating {num_frames} frames at {width}x{height}...")
    
    if seed is not None:
        torch.manual_seed(seed)
        np.random.seed(seed)
        print(f"🎲 Using seed: {seed}")
    
    # Determine device based on CUDA availability
    has_cuda = torch.cuda.is_available()
    
    if has_cuda:
        device = "cuda"
        torch_dtype = torch.float16  # Use float16 to save memory
        print(f"✅ Using GPU for generation: {torch.cuda.get_device_name(0)}")
        
        # Estimate memory requirements (rough estimate)
        # SD model ~2GB + overhead per frame
        gpu_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)  # Convert to GB
        
        if gpu_mem < 8:
            print(f"⚠️ Low GPU memory detected ({gpu_mem:.2f}GB). Using smaller batch size.")
            num_inference_steps = 20  # Fewer steps to save memory
            print(f"ℹ️ Reduced inference steps to {num_inference_steps} for better performance")
        else:
            num_inference_steps = 30
            print(f"ℹ️ Using {num_inference_steps} inference steps")
    else:
        device = "cpu"
        torch_dtype = torch.float32  # CPU works better with float32
        print("⚠️ Using CPU (CUDA not available)")
        num_inference_steps = 20  # Fewer steps for CPU to be faster
    
    try:
        # Load the pipeline
        pipeline_id = "stabilityai/stable-video-diffusion-img2vid-xt"
        
        print(f"🔄 Loading model: {pipeline_id}")
        
        pipe = DiffusionPipeline.from_pretrained(
            pipeline_id,
            torch_dtype=torch_dtype,
            use_safetensors=True,
            cache_dir=MODEL_CACHE_DIR,
            resume_download=True
        )
        
        # Use a more stable scheduler - the DPMSolverMultistepScheduler was causing index errors
        from diffusers import DDIMScheduler
        pipe.scheduler = DDIMScheduler.from_config(pipe.scheduler.config)
        print("✅ Using DDIM scheduler for better stability")
        
        # Move to the appropriate device
        pipe = pipe.to(device)
        
        # Enable memory optimization techniques
        # Disable xformers for SVD as it can cause CUDA configuration errors
        pipe.enable_attention_slicing()
        print("✅ Using attention slicing for stable video diffusion")
        
        if has_cuda:
            # Enable model CPU offload to reduce VRAM usage
            try:
                pipe.enable_model_cpu_offload()
                print("✅ Enabled model CPU offload for better memory management")
            except Exception as e:
                print(f"⚠️ Could not enable model CPU offload: {e}")
            
            # Enable VAE slicing for better memory efficiency
            try:
                pipe.enable_vae_slicing()
                print("✅ Enabled VAE slicing for better memory efficiency")
            except Exception as e:
                print(f"⚠️ Could not enable VAE slicing: {e}")
        
        # For the StableDiffusionPipeline (image generation), xformers is still okay to use
        if has_cuda:
            try:
                import xformers
            except ImportError:
                pass
        
        # Generate a first frame image from the text prompt
        try:
            from diffusers import StableDiffusionPipeline
            
            print("🖼️ Generating initial image from prompt...")
            
            # For the first frame, use stable diffusion to create an image from the text prompt
            img_pipe = StableDiffusionPipeline.from_pretrained(
                "stabilityai/stable-diffusion-2-1-base",
                torch_dtype=torch_dtype,
                safety_checker=None,
                use_safetensors=True
            ).to(device)
            
            img_pipe.enable_attention_slicing()
            
            # Generate image (StableDiffusionPipeline supports guidance_scale)
            image = img_pipe(
                prompt=prompt,
                negative_prompt=negative_prompt,
                num_inference_steps=30,
                width=width,
                height=height,
                guidance_scale=guidance_scale
            ).images[0]
            
            print("✅ Initial image generated")
            
        except Exception as e:
            from PIL import Image
            import random
            
            print(f"⚠️ Error generating initial image with SD: {e}")
            print("⚠️ Using a colored placeholder image instead")
            
            # Create a colored placeholder image
            color = (
                random.randint(0, 255),
                random.randint(0, 255),
                random.randint(0, 255)
            )
            image = Image.new('RGB', (width, height), color=color)
        
        # Save the image to the temp directory
        temp_img_path = os.path.join(temp_dir, "first_frame.png")
        image.save(temp_img_path)
        print(f"💾 Initial frame saved to {temp_img_path}")
        
        # Generate video frames from the image
        print("🎬 Generating video frames...")
        try:
            # Ensure the output paths exist
            os.makedirs(output_dir, exist_ok=True)
            
            # Adjust num_frames based on available memory - more aggressive reduction for stability
            if has_cuda and torch.cuda.get_device_properties(0).total_memory < 8 * (1024**3):  # < 8GB
                adjusted_frames = min(num_frames, 8)  # Reduced from 16 to 8 for better stability
                if adjusted_frames < num_frames:
                    print(f"⚠️ Reduced frames from {num_frames} to {adjusted_frames} due to memory constraints")
                    num_frames = adjusted_frames
            
            # Add a timeout to prevent hanging
            timeout_occurred = [False]
            generation_complete = [False]
            
            # Define timeout handler
            def check_timeout():
                # Much longer timeout (30 minutes) since we know it's very slow
                for _ in range(6):  # Check every 5 minutes for 30 minutes total
                    time.sleep(300)  # 5 minute sleep between checks
                    if generation_complete[0]:
                        return  # Exit if generation completed
                    print("\n📊 Generation still in progress but taking a long time.")
                    print("⏳ This is normal with limited GPU memory. Continuing to wait...")
                
                # Only if we've waited the full 30 minutes and it's still not done
                if not generation_complete[0]:
                    timeout_occurred[0] = True
                    print("\n⚠️ Generation has been running for 30 minutes with no completion.")
                    print("⚠️ You can continue waiting or interrupt with Ctrl+C")
            
            # Start timeout thread
            timeout_thread = threading.Thread(target=check_timeout)
            timeout_thread.daemon = True
            timeout_thread.start()
            
            # Create a progress bar
            progress_bar = tqdm(total=num_inference_steps, desc="Generating video frames")
            
            # Progress callback for StableVideoDiffusionPipeline
            def callback_fn(step, timestep, latents):
                progress_bar.update(1)
                # Check if timeout occurred
                if timeout_occurred[0]:
                    # Return False to stop generation
                    return False
                return True
            
            # Generate video frames with reduced memory settings
            try:
                print("⏳ Starting video generation. This may take several minutes...")
                start_time = time.time()
                video_frames = pipe(
                    image,
                    num_inference_steps=num_inference_steps,
                    num_frames=num_frames,
                    motion_bucket_id=motion_bucket_id,  # Use quality or default value
                    noise_aug_strength=noise_aug_strength,  # Use quality or default value
                    decode_chunk_size=1  # Process one frame at a time (minimum possible)
                ).frames[0]
                generation_complete[0] = True
                generation_time = time.time() - start_time
                print(f"✅ Generation completed in {generation_time:.1f} seconds")
            except IndexError as e:
                # Handle the specific index error that occurs at the end of generation
                if "index 21 is out of bounds" in str(e) or "index out of bounds" in str(e):
                    print("\n⚠️ Encountered a known scheduler issue at the end of generation.")
                    print("⚠️ This typically happens when generation is nearly complete. Using available frames.")
                    try:
                        # Try to get the frames from the pipeline's last step
                        from diffusers.pipelines.stable_video_diffusion.pipeline_stable_video_diffusion import StableVideoDiffusionPipelineOutput
                        video_frames = pipe.decode_latents(pipe.latents)
                        generation_complete[0] = True
                        print("✅ Successfully recovered frames from the pipeline")
                    except Exception:
                        print("❌ Could not recover frames, generation failed")
                        raise
                else:
                    print(f"\n❌ Error during generation: {e}")
                    raise
            except Exception as e:
                print(f"\n❌ Error during generation: {e}")
                raise
            
            # Save frames as separate images
            frame_paths = []
            for i, frame in enumerate(video_frames):
                frame_path = os.path.join(temp_dir, f"frame_{i:04d}.png")
                frame.save(frame_path)
                frame_paths.append(frame_path)
            
            print(f"✅ Generated {len(frame_paths)} frames successfully")
            return frame_paths, image, fps
            
        except RuntimeError as e:
            if "out of memory" in str(e).lower() and has_cuda:
                print("⚠️ GPU out of memory error!")
                
                # Try with fewer frames - more aggressive reduction
                adjusted_frames = max(int(num_frames * 0.5), 4)  # Reduced minimum from 8 to 4
                print(f"🔄 Retrying with absolute minimum frames: {adjusted_frames}")
                
                # Move to CPU if needed
                if adjusted_frames < 8:
                    print("⚠️ Moving to CPU for processing (very slow)")
                    pipe = pipe.to("cpu")
                    torch_dtype = torch.float32  # CPU works better with float32
                    has_cuda = False
                
                # Add a timeout to prevent hanging
                timeout_occurred = [False]
                generation_complete = [False]
                
                # Define timeout handler
                def check_timeout():
                    # Much longer timeout (30 minutes) since we know it's very slow
                    for _ in range(6):  # Check every 5 minutes for 30 minutes total
                        time.sleep(300)  # 5 minute sleep between checks
                        if generation_complete[0]:
                            return  # Exit if generation completed
                        print("\n📊 Generation still in progress but taking a long time.")
                        print("⏳ This is normal with limited GPU memory. Continuing to wait...")
                    
                    # Only if we've waited the full 30 minutes and it's still not done
                    if not generation_complete[0]:
                        timeout_occurred[0] = True
                        print("\n⚠️ Generation has been running for 30 minutes with no completion.")
                        print("⚠️ You can continue waiting or interrupt with Ctrl+C")
                
                # Start timeout thread
                timeout_thread = threading.Thread(target=check_timeout)
                timeout_thread.daemon = True
                timeout_thread.start()
                
                # Create a progress bar
                progress_bar = tqdm(total=20, desc="Generating video frames (reduced)")
                
                def callback_fn_reduced(step, timestep, latents):
                    progress_bar.update(1)
                    return True
                
                # Generate video frames with absolute minimum memory settings
                try:
                    print("⏳ Starting video generation. This may take several minutes...")
                    print("ℹ️ Using absolute minimum memory settings (decode_chunk_size=1)")
                    start_time = time.time()
                    video_frames = pipe(
                        image,
                        num_inference_steps=num_inference_steps,
                        num_frames=num_frames,
                        motion_bucket_id=40,  # Even lower motion value for stability
                        noise_aug_strength=0.1,  # Controls similarity to original image
                        decode_chunk_size=1  # Process one frame at a time (minimum possible)
                    ).frames[0]
                    generation_complete[0] = True
                    generation_time = time.time() - start_time
                    print(f"✅ Generation completed in {generation_time:.1f} seconds")
                except Exception as e:
                    print(f"\n❌ Error during generation: {e}")
                    raise
                
                # Remove the progress bar code that uses callbacks which causes errors
                
                # Generate video frames with absolute minimum memory settings
                try:
                    print("⏳ Retrying with absolute minimum settings...")
                    print(f"ℹ️ Generating {adjusted_frames} frames with 1-frame-at-a-time processing")
                    start_time = time.time()
                    video_frames = pipe(
                        image,
                        num_inference_steps=15,  # Further reduced steps for stability
                        num_frames=adjusted_frames,
                        motion_bucket_id=30,  # Minimal motion value for stability
                        noise_aug_strength=0.05,  # Lower noise for stability
                        decode_chunk_size=1  # Process one frame at a time (absolute minimum)
                    ).frames[0]
                    generation_complete[0] = True
                    generation_time = time.time() - start_time
                    print(f"✅ Generation completed in {generation_time:.1f} seconds")
                except Exception as e:
                    print(f"\n❌ Error during retry with minimum settings: {e}")
                    raise
                
                # Save frames
                frame_paths = []
                for i, frame in enumerate(video_frames):
                    frame_path = os.path.join(temp_dir, f"frame_{i:04d}.png")
                    frame.save(frame_path)
                    frame_paths.append(frame_path)
                
                print(f"✅ Generated {len(frame_paths)} frames successfully (reduced)")
                return frame_paths, image, fps
            else:
                raise
    
    except Exception as e:
        print(f"❌ Error generating video frames: {e}")
        import traceback
        traceback.print_exc()
        return None, None, fps

def create_video_from_frames(frame_paths, output_path, fps=24):
    """Combine frames into a video using ffmpeg"""
    if not frame_paths:
        print("❌ No frames to convert to video")
        return False
    
    try:
        # Create a pattern for the frames
        frame_dir = os.path.dirname(frame_paths[0])
        
        # Use FFmpeg to create a high-quality video
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-pattern_type", "glob",
            "-i", os.path.join(frame_dir, "frame_*.png"),
            "-c:v", "libx264",
            "-preset", "slow",  # Better quality, but slower encoding
            "-crf", "18",       # Lower CRF = Higher quality (range 0-51)
            "-pix_fmt", "yuv420p",
            output_path
        ]
        
        print("🔄 Creating video with FFmpeg...")
        process = subprocess.run(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if process.returncode == 0:
            print(f"✅ Video saved to: {output_path}")
            return True
        else:
            print(f"❌ FFmpeg error: {process.stderr}")
            return False
    
    except Exception as e:
        print(f"❌ Error creating video: {e}")
        return False

def improve_frames(frame_paths, temp_dir):
    """Simple frame interpolation/enhancement (if OpenCV is available)"""
    try:
        import cv2
        import numpy as np
        from PIL import Image
        
        print("🔄 Applying frame enhancement...")
        
        enhanced_paths = []
        for i, frame_path in enumerate(frame_paths):
            # Skip first frame
            if i == 0:
                enhanced_paths.append(frame_path)
                continue
                
            # Read current and previous frames
            current = cv2.imread(frame_path)
            previous = cv2.imread(frame_paths[i-1])
            
            # Apply simple frame blending for smoother transitions
            alpha = 0.85  # Weight for current frame
            blended = cv2.addWeighted(current, alpha, previous, 1-alpha, 0)
            
            # Enhance colors slightly
            hsv = cv2.cvtColor(blended, cv2.COLOR_BGR2HSV)
            hsv[:,:,1] = hsv[:,:,1] * 1.2  # Increase saturation
            hsv[:,:,1] = np.clip(hsv[:,:,1], 0, 255)
            enhanced = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
            
            # Save enhanced frame
            enhanced_path = os.path.join(temp_dir, f"enhanced_{i:04d}.png")
            cv2.imwrite(enhanced_path, enhanced)
            enhanced_paths.append(enhanced_path)
            
        if len(enhanced_paths) == len(frame_paths):
            print(f"✅ Enhanced {len(enhanced_paths)} frames")
            return enhanced_paths
        else:
            print("⚠️ Frame enhancement incomplete, using original frames")
            return frame_paths
            
    except Exception as e:
        print(f"⚠️ Frame enhancement failed: {e}")
        return frame_paths  # Fall back to original frames

def generate_video(
    prompt,
    negative_prompt="poor quality, distorted, blurry, bad, ugly",
    width=512,
    height=512,
    duration=5,
    fps=24,
    seed=None,
    output_dir=DEFAULT_OUTPUT_DIR,
    enhance=True,
    low_memory=False,  # Extremely low memory mode
    quality_mode=False  # New parameter for quality over quantity
):
    """Generate a video from a text prompt"""
    # Enhance prompt with cinematic terms for better quality
    enhanced_prompt = f"{prompt}, cinematic lighting, detailed, high quality"
    print(f"🎬 Generating video for prompt: \"{enhanced_prompt}\"")
    
    # Set extremely low memory mode if requested
    if low_memory:
        print("⚠️ Low memory mode enabled - using minimum resource settings")
        # Override settings for very low memory
        width = min(width, 384)  # Reduce resolution
        height = min(height, 384)
        duration = min(duration, 2)  # Very short video
        fps = min(fps, 8)  # Low fps
    
    # Set quality mode if requested
    if quality_mode:
        print("🔍 Quality mode enabled - prioritizing quality over length")
        # Override settings for quality focus
        width = 512  # Keep good resolution
        height = 512
        duration = min(duration, 2)  # Short but high quality
        fps = 8  # Fewer frames needed
        
        # Set specific generation parameters for quality mode
        try:
            import torch
            gpu_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)  # Convert to GB
            
            # Customize quality settings based on available memory
            if gpu_mem > 6: # For 8GB cards like RTX 4070 Laptop
                print("💎 Using optimized high-quality settings for your GPU")
                # Will be passed to generate_video_frames
                global QUALITY_SETTINGS
                QUALITY_SETTINGS = {
                    "motion_bucket_id": 80,  # Higher motion for more interesting movement
                    "noise_aug_strength": 0.15,  # More creative variation
                    "num_inference_steps": 30,  # More steps for better quality
                    "decode_chunk_size": 1,  # Process one frame at a time
                    "num_frames": 8,  # Fewer frames, but higher quality
                    "guidance_scale": 7.5  # For initial image generation
                }
        except Exception as e:
            print(f"⚠️ Could not determine optimal quality settings: {e}")
            pass
    
    # Install dependencies
    install_success = install_requirements()
    if not install_success:
        print("❌ Failed to install required dependencies")
        return None
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Create a temporary directory for frames
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"📁 Using temporary directory: {temp_dir}")
        
        # Calculate number of frames based on duration and fps
        num_frames = min(int(duration * fps), MAX_FRAMES)
        
        # Generate frames
        frame_paths, first_frame, actual_fps = generate_video_frames(
            prompt=enhanced_prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            num_frames=num_frames,
            fps=fps,
            seed=seed,
            output_dir=output_dir,
            temp_dir=temp_dir,
            quality_mode=quality_mode
        )
        
        if not frame_paths:
            print("❌ Failed to generate video frames")
            return None
            
        # Apply frame enhancement if requested and if there are at least 2 frames
        if enhance and len(frame_paths) > 1:
            try:
                enhanced_paths = improve_frames(frame_paths, temp_dir)
                if enhanced_paths and len(enhanced_paths) == len(frame_paths):
                    frame_paths = enhanced_paths
            except Exception as e:
                print(f"⚠️ Enhancement failed: {e}")
        
        # Create timestamp for the output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        clean_prompt = "".join(c if c.isalnum() or c in [' ', '_', '-'] else '_' for c in prompt[:30])
        video_filename = f"video_{clean_prompt}_{timestamp}.mp4"
        video_path = os.path.join(output_dir, video_filename)
        
        # Create video from frames
        success = create_video_from_frames(frame_paths, video_path, fps=actual_fps)
        
        if success:
            # Save the first frame as a thumbnail
            thumbnail_path = os.path.join(output_dir, f"thumb_{clean_prompt}_{timestamp}.png")
            try:
                first_frame.save(thumbnail_path)
                print(f"✅ Thumbnail saved to: {thumbnail_path}")
            except Exception as e:
                print(f"⚠️ Could not save thumbnail: {e}")
                
            # Save generation info for reference
            try:
                info = {
                    "prompt": prompt,
                    "timestamp": timestamp,
                    "frames": len(frame_paths),
                    "duration": duration,
                    "fps": fps,
                    "seed": seed if seed is not None else "random"
                }
                info_path = os.path.join(output_dir, f"info_{clean_prompt}_{timestamp}.json")
                with open(info_path, 'w') as f:
                    json.dump(info, f, indent=2)
            except Exception as e:
                print(f"⚠️ Could not save info: {e}")
            
            return video_path
    
    return None

def main():
    parser = argparse.ArgumentParser(description="Generate videos from text prompts using AI")
    parser.add_argument("prompt", nargs="?", type=str, help="Text prompt describing the video to generate")
    parser.add_argument("--negative-prompt", type=str, default="poor quality, distorted, blurry, bad, ugly", help="Negative prompt to avoid certain characteristics")
    parser.add_argument("--width", type=int, default=512, help="Video width (default: 512)")
    parser.add_argument("--height", type=int, default=512, help="Video height (default: 512)")
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION, help=f"Video duration in seconds (default: {DEFAULT_DURATION}s)")
    parser.add_argument("--fps", type=int, default=DEFAULT_FPS, help=f"Frames per second (default: {DEFAULT_FPS})")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    parser.add_argument("--output-dir", type=str, default=DEFAULT_OUTPUT_DIR, help="Directory to save generated videos")
    parser.add_argument("--no-enhance", action="store_true", help="Disable frame enhancement")
    parser.add_argument("--low-memory", action="store_true", help="Use absolute minimum memory settings")
    parser.add_argument("--quality-mode", action="store_true", help="Focus on quality over quantity of frames")
    args = parser.parse_args()
    
    # Check if a prompt was provided
    if not args.prompt:
        print("❌ No prompt provided. Please specify a prompt.")
        print("Example: python video_generation.py 'A beautiful sunset over mountains'")
        return 1
    
    # Generate video
    video_path = generate_video(
        prompt=args.prompt,
        negative_prompt=args.negative_prompt,
        width=args.width,
        height=args.height,
        duration=args.duration,
        fps=args.fps,
        seed=args.seed,
        output_dir=args.output_dir,
        enhance=not args.no_enhance,
        low_memory=args.low_memory,
        quality_mode=args.quality_mode
    )
    
    if video_path:
        print(f"✨ Video generation completed successfully!")
        print_versions()
        
        # Add a message if we used CPU but have GPU hardware
        try:
            import torch
            if not torch.cuda.is_available() and check_cuda():
                print("\n🔄 NOTE: This video was generated on CPU but an NVIDIA GPU was detected.")
                print("🔄 CUDA support was installed successfully but requires a restart of the Python environment.")
                print("🔄 Please run the script again to utilize GPU acceleration for faster video generation.")
        except ImportError:
            pass
        
        return 0
    else:
        print("❌ Video generation failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())