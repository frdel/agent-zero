#!/usr/bin/env python3

import argparse
import os
import sys
import subprocess
import time
from datetime import datetime
import json # Added for parsing pip list output
import threading

# Define constants
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Old VENV_DIR calculation:
# VENV_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "..", "instruments_venv")
# New VENV_DIR: Absolute path as defined in Dockerfile.cuda
VENV_DIR = "/opt/instruments_venv"

DEFAULT_OUTPUT_DIR = "/root/generated_images" # Added back
MODEL_CACHE_DIR = os.path.expanduser("~/.cache/stable-diffusion")

# Define constants for PyTorch installation
SHOULD_INSTALL_PYTORCH_CUDA_ON_HOST_CUDA = True  # True to install CUDA version of PyTorch if host has CUDA - Added back
TARGET_TORCH_PREFIX = "2.6.0" # Major.Minor.Patch, e.g., "2.0.1"
TARGET_TORCH_CUDA_INSTALL_SPEC = "torch==2.6.0+cu124" # Exact spec for CUDA install attempt

def get_venv_python_executable(venv_dir_path):
    """Gets the path to the Python executable in the virtual environment."""
    if sys.platform == "win32":
        return os.path.join(venv_dir_path, "Scripts", "python.exe")
    else:
        return os.path.join(venv_dir_path, "bin", "python")

venv_python_exe = get_venv_python_executable(VENV_DIR) # Initialize globally

# --- VENV Robustness Debug ---
print("[DEBUG] Current Python:", sys.executable)
print("[DEBUG] Expected venv Python:", venv_python_exe)
if not os.path.exists(venv_python_exe):
    print(f"❌ [FATAL] Expected venv Python does not exist: {venv_python_exe}")
    sys.exit(1)
if not os.access(venv_python_exe, os.X_OK):
    print(f"❌ [FATAL] Expected venv Python is not executable: {venv_python_exe}")
    sys.exit(1)

def check_cuda():
    """Check if NVIDIA GPU and CUDA are likely available on the host"""
    try:
        # Check if nvidia-smi command works
        nvidia_smi = subprocess.run(['nvidia-smi'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        if nvidia_smi.returncode == 0:
            print("✅ Host NVIDIA GPU detected via nvidia-smi.")
            return True
        print("ℹ️ nvidia-smi command failed or returned non-zero. Assuming no NVIDIA GPU for PyTorch CUDA install.")
        return False
    except FileNotFoundError:
        print("ℹ️ nvidia-smi command not found. Assuming no NVIDIA GPU for PyTorch CUDA install.")
        return False
    except subprocess.TimeoutExpired:
        print("⚠️ Timeout running nvidia-smi. Assuming no NVIDIA GPU for PyTorch CUDA install.")
        return False
    except Exception as e:
        print(f"⚠️ Error running nvidia-smi: {e}. Assuming no NVIDIA GPU for PyTorch CUDA install.")
        return False

# Helper function to get installed packages
def get_installed_packages(venv_python_exe):
    """Gets a dictionary of installed packages and their versions in the venv."""
    cmd = [venv_python_exe, "-m", "pip", "list", "--format=json", "--disable-pip-version-check"]
    print(f"🔍 Checking installed packages in instruments venv...") # Updated message
    try:
        process = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60)
        installed_list = json.loads(process.stdout)
        return {pkg['name'].lower(): pkg['version'] for pkg in installed_list} # Lowercase names
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Failed to list installed packages. Pip STDERR (truncated): {e.stderr[:500]}")
        return {}
    except subprocess.TimeoutExpired:
        print("⚠️ Timeout while listing installed packages.")
        return {}
    except json.JSONDecodeError as e:
        print(f"⚠️ Failed to parse JSON from pip list: {e}")
        return {}
    except Exception as e:
        print(f"❌ Unexpected error listing packages: {e}")
        return {}

# Helper to verify PyTorch CUDA status in the venv
def verify_venv_pytorch_cuda(venv_python_exe):
    """Checks if torch.cuda.is_available() is True in the venv."""
    print("🔍 Verifying PyTorch CUDA status in instruments venv (this might take a moment for initial torch import)...") # Updated message
    try:
        script = "import torch; print(torch.cuda.is_available())"
        result = subprocess.run(
            [venv_python_exe, "-c", script],
            capture_output=True, text=True, check=True, timeout=120 # Increased timeout to 120 seconds
        )
        available = result.stdout.strip().lower() == "true"
        print(f"ℹ️ PyTorch CUDA in instruments venv reports: {'Available' if available else 'Not Available'}") # Updated message
        return available
    except subprocess.TimeoutExpired:
        print(f"⚠️ PyTorch CUDA status check in instruments venv timed out after 120 seconds.") # Updated message
        return False
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Error verifying PyTorch CUDA status in instruments venv: {e.stderr}") # Updated message
        return False

CORE_DEPENDENCIES = { # Ensure this is defined before use in install_requirements
    "huggingface_hub": "0.20.3",
    "safetensors": "0.4.1",
    "accelerate": "0.21.0",
    "diffusers": "0.25.0",
    "transformers": "4.38.2",
    "scipy": "1.15.2" # For diffusers and other potential uses
}

# Optional, for specific features or performance
XFORMERS_VERSION = "0.0.29.post3"

def heartbeat_printer(stop_event, message="⏳ Process still running. Monitor terminal for output.", interval=9):
    while not stop_event.is_set():
        time.sleep(interval)
        if not stop_event.is_set():
            print(message)

def install_requirements(venv_python_exe):
    """Install required packages into the virtual environment, checking versions first."""
    print(f"🔄 Checking/installing dependencies into venv: {VENV_DIR}")

    installed_pkgs = get_installed_packages(venv_python_exe)

    # --- Target Versions Definitions ---
    # For PyTorch, the version check is more about the prefix and CUDA capability.
    # TARGET_TORCH_VERSION_PREFIX is used to check if a reasonably modern torch is installed.
    TARGET_TORCH_PREFIX = "2.6.0" # Major.Minor.Patch, e.g., "2.0.1"
    TARGET_TORCH_CUDA_INSTALL_SPEC = "torch==2.6.0+cu124" # Exact spec for CUDA install attempt

    CORE_DEPENDENCIES = {
        "huggingface_hub": "0.20.3",
        "safetensors": "0.4.1",
        "accelerate": "0.21.0"
    }
    MAIN_DEPENDENCIES = {
        "diffusers": "0.25.0",
        "transformers": "4.38.2",
        "scipy": "1.15.2"
    }
    XFORMERS_VERSION = "0.0.29.post3"

    def run_pip_command(command_args, action_desc, processing_message_interval=20, overall_timeout=6000):
        # Add -v for more verbose pip output and -u for unbuffered Python output for pip itself
        cmd = [venv_python_exe, "-u", "-m", "pip", "-v"] + command_args 
        print(f"🔄 Running: {' '.join(cmd)}")
        
        process = None # Initialize process variable
        try:
            # stdout and stderr will go to console by default
            process = subprocess.Popen(cmd, text=True, encoding='utf-8', errors='replace')
            
            start_time = time.time()
            last_message_time = start_time
            
            while True:
                current_time = time.time()
                
                # Check for overall timeout
                if current_time - start_time > overall_timeout:
                    print(f"⚠️ Timeout ({overall_timeout}s) reached for: {action_desc}")
                    if process:
                        process.terminate()
                        try:
                            process.wait(timeout=5) # Give it a moment to terminate
                        except subprocess.TimeoutExpired:
                            print(f"Killing pip process for '{action_desc}' after terminate timeout.")
                            process.kill()
                            process.wait() # Wait for kill to complete
                    print(f"⚠️ Pip process for '{action_desc}' was terminated/killed due to timeout.")
                    return False

                # Check if process finished
                if process:
                    return_code = process.poll()
                    if return_code is not None:
                        if return_code == 0:
                            print(f"✅ Successfully {action_desc}")
                            return True
                        else:
                            print(f"⚠️ Failed to {action_desc}. Pip process exited with code: {return_code}")
                            # Pip's own error messages should have already printed to console
                            return False
                else: # Should not happen if Popen succeeds
                    print(f"❌ Error: Popen process object is None for {action_desc}")
                    return False
                # Print "still processing" message
                if current_time - last_message_time > processing_message_interval:
                    print(f"⏳ Still processing: {action_desc} (running for {int(current_time - start_time)}s)...")
                    last_message_time = current_time
                time.sleep(1) # Poll interval

        except FileNotFoundError:
            print(f"❌ Error: The command '{cmd[0]}' was not found. Is Python/pip correctly set up in the venv path?")
            return False
        except Exception as e:
            print(f"❌ Unexpected error during pip process for {action_desc}: {e}")
            if process and process.poll() is None: # If process is still running after an unexpected error
                print(f"Terminating hanging pip process for '{action_desc}' due to unexpected error.")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            return False

    # --- PyTorch Bundle Installation Logic ---
    host_has_cuda = check_cuda()
    pytorch_installed_version = installed_pkgs.get("torch")
    
    reinstall_pytorch_bundle = False
    
    if pytorch_installed_version:
        print(f"ℹ️ Found existing PyTorch version: {pytorch_installed_version} in instruments venv.") # Updated message
        # Check if major.minor matches and if CUDA status is as expected
        if not pytorch_installed_version.startswith(TARGET_TORCH_PREFIX.split('.')[0] + '.' + TARGET_TORCH_PREFIX.split('.')[1]):
            print(f"⚠️ Existing PyTorch version {pytorch_installed_version} prefix does not match target {TARGET_TORCH_PREFIX}. Will reinstall.")
            reinstall_pytorch_bundle = True
        else:
            # Version prefix matches, now check CUDA status
            venv_pytorch_has_cuda = verify_venv_pytorch_cuda(venv_python_exe)
            if SHOULD_INSTALL_PYTORCH_CUDA_ON_HOST_CUDA and host_has_cuda and not venv_pytorch_has_cuda:
                print(f"⚠️ Host has CUDA, but PyTorch in instruments venv is NOT CUDA-functional. Will reinstall for CUDA.") # Updated message
                reinstall_pytorch_bundle = True
            elif SHOULD_INSTALL_PYTORCH_CUDA_ON_HOST_CUDA and not host_has_cuda and venv_pytorch_has_cuda:
                print(f"⚠️ Host does NOT have CUDA, but PyTorch in instruments venv IS CUDA-functional. Will reinstall for CPU.") # Updated message
                reinstall_pytorch_bundle = True
            elif not SHOULD_INSTALL_PYTORCH_CUDA_ON_HOST_CUDA and venv_pytorch_has_cuda: # We want CPU, but it has CUDA
                print(f"⚠️ PyTorch CUDA installation not desired, but PyTorch in instruments venv IS CUDA-functional. Will reinstall for CPU.") # Updated message
                reinstall_pytorch_bundle = True
            else:
                print(f"✅ Existing PyTorch ({pytorch_installed_version}) in instruments venv meets expectations (CUDA functional: {venv_pytorch_has_cuda}, Host CUDA: {host_has_cuda}).") # Updated message
    else:
        print(f"ℹ️ PyTorch not found in instruments venv. Will install.") # Updated message
        reinstall_pytorch_bundle = True

    if reinstall_pytorch_bundle:
        print("🔄 Preparing to install/reinstall PyTorch bundle (torch, torchvision, torchaudio).")
        
        # Attempt to purge pip cache before critical installations like PyTorch
        print("🧹 Attempting to purge pip cache...")
        # Use a short timeout for cache purge, it should be quick or fail fast.
        run_pip_command(["cache", "purge"], "purged pip cache", overall_timeout=60) 

        for pkg_name in ["torch", "torchvision", "torchaudio"]:
            if installed_pkgs.get(pkg_name.lower()): # Uninstall if present
                run_pip_command(["uninstall", "-y", pkg_name], f"pre-cleaned {pkg_name}")
        
        if SHOULD_INSTALL_PYTORCH_CUDA_ON_HOST_CUDA and host_has_cuda:
            print("✅ Host NVIDIA GPU detected. Attempting to install PyTorch with CUDA support...")
            success = run_pip_command(
                ["install", TARGET_TORCH_CUDA_INSTALL_SPEC, "torchvision", "torchaudio", "--index-url", "https://download.pytorch.org/whl/cu124"],
                f"installed PyTorch with CUDA ({TARGET_TORCH_CUDA_INSTALL_SPEC})"
            )
        else:
            print("ℹ️ Host does not have NVIDIA GPU or CUDA PyTorch install disabled. Installing CPU version of PyTorch...")
            success = run_pip_command(
                ["install", f"torch=={TARGET_TORCH_PREFIX}", "torchvision", "torchaudio"],
                f"installed PyTorch CPU ({TARGET_TORCH_PREFIX})"
            )
        if success:
            # Verify CUDA functionality again after install attempt
            venv_pytorch_has_cuda_after_install = verify_venv_pytorch_cuda(venv_python_exe)
            if SHOULD_INSTALL_PYTORCH_CUDA_ON_HOST_CUDA and host_has_cuda and not venv_pytorch_has_cuda_after_install:
                print(f"⚠️ WARNING: Host has CUDA, but PyTorch in instruments venv is NOT CUDA-functional after installation.") # Updated message
            elif SHOULD_INSTALL_PYTORCH_CUDA_ON_HOST_CUDA and host_has_cuda and venv_pytorch_has_cuda_after_install:
                print(f"✅ PyTorch in instruments venv is CUDA-functional after installation, as expected.") # Updated message
        else:
            print(f"❌ Failed to install PyTorch bundle. See pip errors above.")
            # Consider if script should exit here or try to continue with other deps
    
    # --- Install/Verify other core dependencies ---
    for dep, version_spec in CORE_DEPENDENCIES.items():
        current_version = installed_pkgs.get(dep.lower()) # Ensure consistent key casing
        
        if current_version == version_spec:
            print(f"✅ {dep} ({version_spec}) is already installed and up to date.")
            continue
        
        action = "Installing" if not current_version else f"Updating from {current_version} to"
        print(f"🔄 {action} {dep} to {version_spec}.")
        
        if current_version: # If a version exists but is wrong/different
            if not run_pip_command(["uninstall", "-y", dep], f"uninstalling old {dep} ({current_version})"):
                print(f"⚠️ Failed to uninstall old {dep}. Attempting to install target version anyway.")

        if not run_pip_command(["install", f"{dep}=={version_spec}"], f"installed {dep}=={version_spec}"):
            print(f"❌ Failed to install {dep}=={version_spec}. Aborting dependency installation.")
            return False 

    # --- Xformers (Conditional) ---
    cuda_available_in_venv_pytorch_final = verify_venv_pytorch_cuda(venv_python_exe) 
    if cuda_available_in_venv_pytorch_final:
        current_xformers_version = installed_pkgs.get("xformers")
        if current_xformers_version == XFORMERS_VERSION:
            print(f"✅ xformers ({XFORMERS_VERSION}) is already installed and up to date.")
        else:
            action = "Installing" if not current_xformers_version else f"Updating from {current_xformers_version} to"
            print(f"🔄 {action} xformers to {XFORMERS_VERSION} for better GPU performance...")
            if current_xformers_version:
                run_pip_command(["uninstall", "-y", "xformers"], f"uninstalling old xformers ({current_xformers_version})")
            if not run_pip_command(["install", f"xformers=={XFORMERS_VERSION}"], f"installed xformers=={XFORMERS_VERSION}"):
                print("⚠️ Warning: Failed to install xformers. This is not critical, generation will work without it.")
    else:
        # If xformers is installed but CUDA is not available, uninstall xformers
        if installed_pkgs.get("xformers"):
            print("ℹ️ CUDA not available in PyTorch, but xformers is installed. Uninstalling xformers...")
            run_pip_command(["uninstall", "-y", "xformers"], "uninstalling xformers (CUDA not available)")
        print("ℹ️ Skipping xformers installation as CUDA is not available in the venv's PyTorch.")

    print("✅ Dependency check/installation process complete for venv.")
    return True

def ensure_cpu_dependencies(venv_python_exe):
    """Ensure all required CPU dependencies are installed in the venv."""
    import subprocess, json
    try:
        result = subprocess.run([venv_python_exe, "-m", "pip", "list", "--format=json"], capture_output=True, text=True, check=True)
        pkgs = {pkg['name'].lower(): pkg['version'] for pkg in json.loads(result.stdout)}
    except Exception:
        pkgs = {}
    if "torch" not in pkgs:
        print("🔄 Installing CPU dependencies in venv...")
        subprocess.run([venv_python_exe, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], check=True)
        subprocess.run([
            venv_python_exe, "-m", "pip", "install",
            "torch==2.6.0", "torchvision", "torchaudio",
            "huggingface-hub==0.20.3", "safetensors==0.4.1", "accelerate==0.21.0",
            "diffusers==0.25.0", "transformers==4.38.2", "scipy==1.15.2"
        ], check=True)
        print("✅ CPU dependencies installed.")
    else:
        print("✅ CPU dependencies already installed in venv.")

def manage_venv_and_execution():
    """Ensures script runs in venv, verifies dependencies for GPU workflow, then re-launches if needed."""
    global venv_python_exe # Make sure we update the global if venv is created
    venv_python_exe = get_venv_python_executable(VENV_DIR)

    # If already in venv, continue
    if sys.executable == venv_python_exe:
        print(f"✅ Running in dedicated instruments virtual environment: {VENV_DIR}")
        return True

    # Try to detect if CUDA is available (host and torch)
    cuda_available = False
    try:
        import torch
        cuda_available = torch.cuda.is_available()
    except Exception:
        cuda_available = False

    # If CUDA is available, use Dockerfile pre-created venv workflow (existing logic)
    if cuda_available:
        if not os.path.exists(VENV_DIR):
            print(f"❌ [FATAL] Expected venv for GPU workflow does not exist: {VENV_DIR}")
            sys.exit(1)
        print(f"ℹ️ Instruments virtual environment found at {VENV_DIR}. Verifying dependencies...")
        if not install_requirements(venv_python_exe):
            print(f"❌ Failed to install/verify requirements in existing instruments venv. Please check errors. Exiting.")
            sys.exit(1)
        print(f"🔄 Re-launching script with instruments virtual environment Python: {venv_python_exe}")
        try:
            os.execv(venv_python_exe, [venv_python_exe] + sys.argv)
        except Exception as e:
            print(f"❌ [FATAL] Failed to re-launch script with venv: {e}")
            print(f"👉 Please try activating the venv manually and running the script:")
            print(f"   {venv_python_exe} {' '.join(sys.argv)}")
            sys.exit(1)
        print(f"❌ [FATAL] os.execv should not return, but it did. Exiting.")
        sys.exit(1)
    else:
        # For CPU workflow, assume venv and dependencies are already set up by the shell script
        print(f"✅ Running in CPU workflow with venv already set up at {VENV_DIR}")
        return True

def print_versions():
    """Print installed versions of all relevant packages (expects to run in venv)"""
    # This function now assumes it's running inside the venv due to manage_venv_and_execution
    print("\n📦 Installed Package Versions (from venv):")
    print("-" * 40)

    try:
        import torch
        print(f"PyTorch: {torch.__version__}")
        print(f"CUDA Available (in this PyTorch runtime): {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            cuda_version = getattr(getattr(torch, 'version', None), 'cuda', None)
            print(f"CUDA Version reported by PyTorch: {cuda_version}")
            print(f"cuDNN Version: {torch.backends.cudnn.version() if torch.backends.cudnn.is_available() else 'Not available'}")
            print(f"GPU: {torch.cuda.get_device_name(0)}")
    except ImportError:
        print("PyTorch: Not installed or importable in venv")
    except Exception as e:
        print(f"Error checking PyTorch version: {e}")

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

    # Dependencies are now handled by manage_venv_and_execution ensuring script runs in venv.

    # Import required libraries (should be from venv)
    try:
        import torch
        from diffusers.pipelines.stable_diffusion.pipeline_stable_diffusion import StableDiffusionPipeline # Linter might complain, but this is common for diffusers
        from PIL import Image
    except ImportError as e:
        print(f"❌ Critical Error: Failed to import core libraries (torch, diffusers, PIL) from instruments venv: {e}")
        print(f"Ensure dependencies were installed correctly in the instruments venv: {VENV_DIR}") # Updated message
        sys.exit(1)

    print(f"✅ Using PyTorch {torch.__version__} (from venv)")
    
    # This check is crucial: it reflects the venv's PyTorch CUDA status
    is_cuda_available_runtime = torch.cuda.is_available()
    print(f"✅ CUDA available in current PyTorch runtime: {is_cuda_available_runtime}")

    device = "cpu" # Default to CPU
    if is_cuda_available_runtime:
        device = "cuda"
        try:
            print(f"✅ Attempting to use CUDA device: {torch.cuda.get_device_name(0)}")
            print(f"ℹ️ GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
        except Exception as e:
            print(f"⚠️ Could not get CUDA device_name or properties, but CUDA is available. Proceeding. Error: {e}")
    else:
        # If CUDA is not available in PyTorch, double-check with nvidia-smi for user feedback
        if check_cuda(): # check_cuda uses nvidia-smi
            print("⚠️ PyTorch reports CUDA not available, but nvidia-smi found an NVIDIA GPU.")
            print("⚠️ This might indicate a PyTorch installation issue or driver mismatch within the venv.")
        print("⚠️ Using CPU (CUDA not available in PyTorch runtime or no NVIDIA GPU detected).")


    # Set seed if provided
    if seed is not None:
        torch.manual_seed(seed)
        print(f"🎲 Using seed: {seed}")

    # Load the model
    print("🔄 Loading Stable Diffusion model...")
    start_time = time.time()
    # Heartbeat for model loading
    model_loading_stop = threading.Event()
    model_loading_thread = threading.Thread(target=heartbeat_printer, args=(model_loading_stop,))
    model_loading_thread.start()
    try:
        pipe = StableDiffusionPipeline.from_pretrained(
            "stabilityai/stable-diffusion-2-1-base",
            torch_dtype=torch.float16 if device == "cuda" else torch.float32, # Use float16 for CUDA
            safety_checker=None, # As per original script
            cache_dir=MODEL_CACHE_DIR, # Use the global constant
            resume_download=True,
            use_safetensors=True
        )
    finally:
        model_loading_stop.set()
        model_loading_thread.join()

    try:
        pipe = pipe.to(device)
        print(f"✅ Model successfully moved to {device}.")
        
        # Enable memory optimizations
        pipe.enable_attention_slicing() # Good for both CPU and CUDA

        if device == "cuda":
            # Enable xformers if available (it would have been installed if CUDA was primary target)
            try:
                import xformers # This import is now from the venv
                pipe.enable_xformers_memory_efficient_attention()
                print("✅ Using xformers for memory efficient attention on CUDA.")
            except ImportError:
                print("⚠️ xformers not available in venv or import failed, using standard attention on CUDA.")
            except Exception as e: # Catch other xformers errors
                print(f"⚠️ Error enabling xformers: {e}. Using standard attention.")

    except RuntimeError as e:
        if "CUDA" in str(e).upper() and device == "cuda": # Check if error is CUDA related
            print(f"⚠️ Error moving model to CUDA: {e}")
            print("⚠️ Falling back to CPU for this generation.")
            device = "cpu"
            pipe = pipe.to(device) # Move to CPU
            pipe.enable_attention_slicing() # Ensure attention slicing on CPU too
            # If we fell back to CPU, inform user if they have a GPU
            if check_cuda():
                print("🔄 NOTE: NVIDIA GPU was detected, but an error occurred using CUDA for the model.")
                print("🔄 Generation will proceed on CPU. Check PyTorch/CUDA setup in venv if issues persist.")
        else:
            print(f"❌ Runtime error during model setup or .to(device): {e}")
        raise # Re-raise if not a CUDA OOM or similar fallback scenario
    except Exception as e: # Catch other .to(device) errors
         print(f"❌ Unexpected error during model setup or .to(device): {e}")
         raise


    print(f"✅ Model loaded in {time.time() - start_time:.2f} seconds, configured for {device}")

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Generate the image
    print(f"🔄 Generating image on {device}...")
    gen_start_time = time.time()
    # Heartbeat for image generation
    gen_stop = threading.Event()
    gen_thread = threading.Thread(target=heartbeat_printer, args=(gen_stop,))
    gen_thread.start()
    try:
        with torch.inference_mode():
            output = pipe(
                prompt=prompt,
                num_inference_steps=50 if device == "cuda" else 25, # Adjusted CPU steps
                guidance_scale=9,
                height=size[1],
                width=size[0]
            )
    finally:
        gen_stop.set()
        gen_thread.join()

    # Defensive check for output/images
    image = None
    if isinstance(output, dict) and 'images' in output and isinstance(output['images'], list) and len(output['images']) > 0:
        candidate = output['images'][0]
        if hasattr(candidate, 'save'):
            image = candidate
    elif hasattr(output, 'images') and isinstance(output.images, list) and len(output.images) > 0:
        candidate = output.images[0]
        if hasattr(candidate, 'save'):
            image = candidate
    elif isinstance(output, (tuple, list)) and len(output) > 0 and hasattr(output[0], 'save'):
        image = output[0]
    if image is None:
        raise RuntimeError("Output from pipeline does not contain an image in the expected format.")

    print(f"✅ Image generated on {device} in {time.time() - gen_start_time:.2f} seconds")

    # Save the image
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"image_{timestamp}.png"
    filepath = os.path.join(output_dir, filename)

    if hasattr(image, 'save'):
        image.save(filepath)
    else:
        raise RuntimeError("The generated image object does not have a 'save' method. It may not be a PIL.Image.Image.")
    print(f"💾 Image saved to: {filepath}")

    return filepath

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
        print(f"Example: python {os.path.basename(__file__)} 'A majestic dragon'")
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

        # Add a message if we used CPU but have GPU hardware that PyTorch couldn't use
        try:
            import torch # Should be venv's torch
            if not torch.cuda.is_available() and check_cuda(): # check_cuda for host hardware
                print("\n🔄 NOTE: This image was generated on CPU, but an NVIDIA GPU was detected on the host.")
                print("🔄 If you intended to use GPU, please check the PyTorch and CUDA driver setup within the virtual environment.")
                print(f"🔄 The virtual environment is located at: {VENV_DIR}")
        except ImportError:
            pass # PyTorch import failed, previous errors would have caught this.
        except Exception as e:
            print(f"Note: Error during post-generation GPU check: {e}")

        return 0
    else:
        print("❌ Image generation failed.")
        # Check if we installed CUDA support and a GPU is available but CUDA wasn't recognized by PyTorch
        try:
            import torch
            if not torch.cuda.is_available() and check_cuda():
                print("\nℹ️ NOTE: An NVIDIA GPU was detected on the host, but PyTorch could not use CUDA.")
                print(f"ℹ️ PyTorch (version {torch.__version__}) reported CUDA as unavailable in the current runtime.")
                print(f"ℹ️ Dependencies (including PyTorch with CUDA if hardware was detected) were installed into: {VENV_DIR}")
                print("ℹ️ Please ensure your NVIDIA drivers are up to date and compatible with the PyTorch CUDA version attempted.")
                print("ℹ️ You might need to manually re-trigger dependency installation or debug the venv if issues persist.")
        except ImportError:
            print("ℹ️ PyTorch is not importable. Dependency installation likely failed.")
        except Exception as e:
            print(f"Note: Error during failure analysis: {e}")
        return 1

if __name__ == "__main__":
    # This block ensures that the script runs inside its dedicated virtual environment.
    # If not, it sets up the venv, installs dependencies, and re-launches itself.
    if not manage_venv_and_execution():
        # This part is reached if execv fails, manage_venv_and_execution will print error and exit.
        # However, to be absolutely sure, we can exit here too.
        sys.exit(1) # Exit if re-launch failed (though os.execv doesn't return on success)
    
    # If manage_venv_and_execution() returns True, it means we are already in the venv.
    # Or, if it re-launched, the new process starts from here and manage_venv_and_execution() will return True.
    sys.exit(main())