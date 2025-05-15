#!/usr/bin/env python3

import argparse
import os
import sys
import subprocess
import time
from datetime import datetime
import json
import threading
import torch

# Define constants
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = "/opt/instruments_venv"
DEFAULT_OUTPUT_DIR = "/root/generated_music"
MODEL_CACHE_DIR = os.path.expanduser("~/.cache/audiocraft-models")

# PyTorch/CUDA logic
SHOULD_INSTALL_PYTORCH_CUDA_ON_HOST_CUDA = True
TARGET_TORCH_PREFIX = "2.6.0"
TARGET_TORCH_CUDA_INSTALL_SPEC = "torch==2.6.0+cu124"

# Helper: get venv python

def get_venv_python_executable(venv_dir_path):
    if sys.platform == "win32":
        return os.path.join(venv_dir_path, "Scripts", "python.exe")
    else:
        return os.path.join(venv_dir_path, "bin", "python")

venv_python_exe = get_venv_python_executable(VENV_DIR)

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
    try:
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

def get_installed_packages(venv_python_exe):
    cmd = [venv_python_exe, "-m", "pip", "list", "--format=json", "--disable-pip-version-check"]
    print(f"🔍 Checking installed packages in instruments venv...")
    try:
        process = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60)
        installed_list = json.loads(process.stdout)
        return {pkg['name'].lower(): pkg['version'] for pkg in installed_list}
    except Exception as e:
        print(f"❌ Unexpected error listing packages: {e}")
        return {}

def verify_venv_pytorch_cuda(venv_python_exe):
    print("🔍 Verifying PyTorch CUDA status in instruments venv (this might take a moment for initial torch import)...")
    try:
        script = "import torch; print(torch.cuda.is_available())"
        result = subprocess.run(
            [venv_python_exe, "-c", script],
            capture_output=True, text=True, check=True, timeout=120
        )
        available = result.stdout.strip().lower() == "true"
        print(f"ℹ️ PyTorch CUDA in instruments venv reports: {'Available' if available else 'Not Available'}")
        return available
    except Exception as e:
        print(f"⚠️ Error verifying PyTorch CUDA status in instruments venv: {e}")
        return False

CORE_DEPENDENCIES = {
    "huggingface_hub": "0.20.3",
    "safetensors": "0.4.1",
    "accelerate": "0.21.0",
    "transformers": "4.38.2",
    "einops": "0.6.1",
    "tqdm": "4.65.0",
    "librosa": "0.10.0.post2",
    "scipy": "1.12.0",
    "numpy": "1.24.3"
}
XFORMERS_VERSION = "0.0.29.post3"

# Heartbeat printer
def heartbeat_printer(stop_event, message="⏳ Process still running. Monitor terminal for output.", interval=9):
    while not stop_event.is_set():
        time.sleep(interval)
        if not stop_event.is_set():
            print(message)

def install_requirements(venv_python_exe):
    print(f"🔄 Checking/installing dependencies into venv: {VENV_DIR}")
    installed_pkgs = get_installed_packages(venv_python_exe)
    TARGET_TORCH_PREFIX = "2.6.0"
    TARGET_TORCH_CUDA_INSTALL_SPEC = "torch==2.6.0+cu124"
    def run_pip_command(command_args, action_desc, processing_message_interval=20, overall_timeout=6000):
        cmd = [venv_python_exe, "-u", "-m", "pip", "-v"] + command_args
        print(f"🔄 Running: {' '.join(cmd)}")
        process = None
        try:
            process = subprocess.Popen(cmd, text=True, encoding='utf-8', errors='replace')
            start_time = time.time()
            last_message_time = start_time
            while True:
                current_time = time.time()
                if current_time - start_time > overall_timeout:
                    print(f"⚠️ Timeout ({overall_timeout}s) reached for: {action_desc}")
                    if process:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            print(f"Killing pip process for '{action_desc}' after terminate timeout.")
                            process.kill()
                            process.wait()
                    print(f"⚠️ Pip process for '{action_desc}' was terminated/killed due to timeout.")
                    return False
                if process:
                    return_code = process.poll()
                    if return_code is not None:
                        if return_code == 0:
                            print(f"✅ Successfully {action_desc}")
                            return True
                        else:
                            print(f"⚠️ Failed to {action_desc}. Pip process exited with code: {return_code}")
                            return False
                else:
                    print(f"❌ Error: Popen process object is None for {action_desc}")
                    return False
                if current_time - last_message_time > processing_message_interval:
                    print(f"⏳ Still processing: {action_desc} (running for {int(current_time - start_time)}s)...")
                    last_message_time = current_time
                time.sleep(1)
        except FileNotFoundError:
            print(f"❌ Error: The command '{cmd[0]}' was not found. Is Python/pip correctly set up in the venv path?")
            return False
        except Exception as e:
            print(f"❌ Unexpected error during pip process for {action_desc}: {e}")
            if process and process.poll() is None:
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
        print(f"ℹ️ Found existing PyTorch version: {pytorch_installed_version} in instruments venv.")
        if not pytorch_installed_version.startswith(TARGET_TORCH_PREFIX.split('.')[0] + '.' + TARGET_TORCH_PREFIX.split('.')[1]):
            print(f"⚠️ Existing PyTorch version {pytorch_installed_version} prefix does not match target {TARGET_TORCH_PREFIX}. Will reinstall.")
            reinstall_pytorch_bundle = True
        else:
            venv_pytorch_has_cuda = verify_venv_pytorch_cuda(venv_python_exe)
            if SHOULD_INSTALL_PYTORCH_CUDA_ON_HOST_CUDA and host_has_cuda and not venv_pytorch_has_cuda:
                print(f"⚠️ Host has CUDA, but PyTorch in instruments venv is NOT CUDA-functional. Will reinstall for CUDA.")
                reinstall_pytorch_bundle = True
            elif SHOULD_INSTALL_PYTORCH_CUDA_ON_HOST_CUDA and not host_has_cuda and venv_pytorch_has_cuda:
                print(f"⚠️ Host does NOT have CUDA, but PyTorch in instruments venv IS CUDA-functional. Will reinstall for CPU.")
                reinstall_pytorch_bundle = True
            elif not SHOULD_INSTALL_PYTORCH_CUDA_ON_HOST_CUDA and venv_pytorch_has_cuda:
                print(f"⚠️ PyTorch CUDA installation not desired, but PyTorch in instruments venv IS CUDA-functional. Will reinstall for CPU.")
                reinstall_pytorch_bundle = True
            else:
                print(f"✅ Existing PyTorch ({pytorch_installed_version}) in instruments venv meets expectations (CUDA functional: {venv_pytorch_has_cuda}, Host CUDA: {host_has_cuda}).")
    else:
        print(f"ℹ️ PyTorch not found in instruments venv. Will install.")
        reinstall_pytorch_bundle = True
    if reinstall_pytorch_bundle:
        print("🔄 Preparing to install/reinstall PyTorch bundle (torch, torchvision, torchaudio).")
        print("🧹 Attempting to purge pip cache...")
        run_pip_command(["cache", "purge"], "purged pip cache", overall_timeout=60)
        for pkg_name in ["torch", "torchvision", "torchaudio"]:
            if installed_pkgs.get(pkg_name.lower()):
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
            venv_pytorch_has_cuda_after_install = verify_venv_pytorch_cuda(venv_python_exe)
            if SHOULD_INSTALL_PYTORCH_CUDA_ON_HOST_CUDA and host_has_cuda and not venv_pytorch_has_cuda_after_install:
                print(f"⚠️ WARNING: Host has CUDA, but PyTorch in instruments venv is NOT CUDA-functional after installation.")
            elif SHOULD_INSTALL_PYTORCH_CUDA_ON_HOST_CUDA and host_has_cuda and venv_pytorch_has_cuda_after_install:
                print(f"✅ PyTorch in instruments venv is CUDA-functional after installation, as expected.")
        else:
            print(f"❌ Failed to install PyTorch bundle. See pip errors above.")
    # --- Install/Verify other core dependencies ---
    for dep, version_spec in CORE_DEPENDENCIES.items():
        current_version = installed_pkgs.get(dep.lower())
        if current_version == version_spec:
            print(f"✅ {dep} ({version_spec}) is already installed and up to date.")
            continue
        action = "Installing" if not current_version else f"Updating from {current_version} to"
        print(f"🔄 {action} {dep} to {version_spec}.")
        if current_version:
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
        if installed_pkgs.get("xformers"):
            print("ℹ️ CUDA not available in PyTorch, but xformers is installed. Uninstalling xformers...")
            run_pip_command(["uninstall", "-y", "xformers"], "uninstalling xformers (CUDA not available)")
        print("ℹ️ Skipping xformers installation as CUDA is not available in the venv's PyTorch.")
    print("✅ Dependency check/installation process complete for venv.")
    return True

def manage_venv_and_execution():
    global venv_python_exe
    venv_python_exe = get_venv_python_executable(VENV_DIR)
    if sys.executable == venv_python_exe:
        print(f"✅ Running in dedicated instruments virtual environment: {VENV_DIR}")
        return True
    cuda_available = False
    try:
        import torch
        cuda_available = torch.cuda.is_available()
    except Exception:
        cuda_available = False
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
        print(f"✅ Running in CPU workflow with venv already set up at {VENV_DIR}")
        return True

def print_versions():
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
    print("-" * 40)

def generate_music(prompt, output_dir=DEFAULT_OUTPUT_DIR, duration=None, seed=None):
    print(f"🎵 Generating music with prompt: \"{prompt}\"")
    try:
        import torch
        from transformers import AutoProcessor, MusicgenForConditionalGeneration
        import scipy.io.wavfile as wavfile
        import numpy as np
        import subprocess
    except ImportError as e:
        print(f"❌ Critical Error: Failed to import core libraries (torch, transformers, scipy, numpy) from instruments venv: {e}")
        print(f"Ensure dependencies were installed correctly in the instruments venv: {VENV_DIR}")
        sys.exit(1)
    print(f"✅ Using PyTorch {torch.__version__} (from venv)")
    is_cuda_available_runtime = torch.cuda.is_available()
    print(f"✅ CUDA available in current PyTorch runtime: {is_cuda_available_runtime}")
    device = "cpu"
    if is_cuda_available_runtime:
        device = "cuda"
        try:
            print(f"✅ Attempting to use CUDA device: {torch.cuda.get_device_name(0)}")
            print(f"ℹ️ GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
        except Exception as e:
            print(f"⚠️ Could not get CUDA device_name or properties, but CUDA is available. Proceeding. Error: {e}")
    else:
        if check_cuda():
            print("⚠️ PyTorch reports CUDA not available, but nvidia-smi found an NVIDIA GPU.")
            print("⚠️ This might indicate a PyTorch installation issue or driver mismatch within the venv.")
        print("⚠️ Using CPU (CUDA not available in PyTorch runtime or no NVIDIA GPU detected).")
    if seed is not None:
        torch.manual_seed(seed)
        print(f"🎲 Using seed: {seed}")
    print("🔄 Loading MusicGen model...")
    start_time = time.time()
    model_loading_stop = threading.Event()
    model_loading_thread = threading.Thread(target=heartbeat_printer, args=(model_loading_stop,))
    model_loading_thread.start()
    try:
        processor = AutoProcessor.from_pretrained("facebook/musicgen-small", cache_dir=MODEL_CACHE_DIR)
        model = MusicgenForConditionalGeneration.from_pretrained("facebook/musicgen-small", cache_dir=MODEL_CACHE_DIR)
    finally:
        model_loading_stop.set()
        model_loading_thread.join()
    try:
        model.to(torch.device(device))
        print(f"✅ Model successfully moved to {device}.")
    except RuntimeError as e:
        if "CUDA" in str(e).upper() and device == "cuda":
            print(f"⚠️ Error moving model to CUDA: {e}")
            print("⚠️ Falling back to CPU for this generation.")
            device = "cpu"
            model.to(torch.device(device))
        else:
            print(f"❌ Runtime error during model setup or .to(device): {e}")
            raise
    except Exception as e:
        print(f"❌ Unexpected error during model setup or .to(device): {e}")
        raise
    print(f"✅ Model loaded in {time.time() - start_time:.2f} seconds, configured for {device}")
    os.makedirs(output_dir, exist_ok=True)
    print(f"🔄 Generating music on {device}...")
    gen_start_time = time.time()
    gen_stop = threading.Event()
    gen_thread = threading.Thread(target=heartbeat_printer, args=(gen_stop,))
    gen_thread.start()
    try:
        inputs = processor(
            text=[prompt],
            padding=True,
            return_tensors="pt",
        )
        # Move each tensor in the BatchEncoding to the correct device
        inputs = {k: v.to(torch.device(device)) if hasattr(v, 'to') else v for k, v in inputs.items()}

        # Determine max_new_tokens allowed by the model
        max_model_tokens = getattr(model.config, 'max_position_embeddings', None)
        if max_model_tokens is None:
            # Try to get from model.config.audio_encoder if available
            audio_encoder = getattr(model.config, 'audio_encoder', None)
            max_model_tokens = getattr(audio_encoder, 'max_position_embeddings', None)
        if max_model_tokens is None:
            max_model_tokens = 1024  # Safe fallback

        # Calculate max_new_tokens from duration if provided
        max_new_tokens = max_model_tokens
        if duration is not None:
            frame_rate = None
            audio_encoder = getattr(model.config, 'audio_encoder', None)
            if audio_encoder is not None and hasattr(audio_encoder, 'frame_rate'):
                frame_rate = audio_encoder.frame_rate
            elif hasattr(model.config, 'frame_rate'):
                frame_rate = model.config.frame_rate
            if frame_rate is not None:
                requested_tokens = int(duration * frame_rate)
                if requested_tokens > max_model_tokens:
                    print(f"⚠️ Requested duration ({duration}s) exceeds model's max token capacity. Clamping to {max_model_tokens / frame_rate:.2f} seconds.")
                max_new_tokens = min(requested_tokens, max_model_tokens)
            else:
                print("⚠️ Could not determine model frame rate. Using model's max token capacity.")
        else:
            print(f"ℹ️ No duration specified. Using model's max token capacity: {max_model_tokens} tokens.")

        with torch.inference_mode():
            audio_values = model.generate(**inputs, max_new_tokens=max_new_tokens)
    finally:
        gen_stop.set()
        gen_thread.join()
    # Robustly extract sampling_rate
    sampling_rate = 32000  # Default fallback
    audio_encoder = getattr(model.config, 'audio_encoder', None)
    if audio_encoder is not None and hasattr(audio_encoder, 'sampling_rate'):
        sampling_rate = audio_encoder.sampling_rate
    elif hasattr(model.config, 'sampling_rate'):
        sampling_rate = model.config.sampling_rate
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"music_{timestamp}.wav"
    filepath = os.path.join(output_dir, filename)
    audio_data = audio_values[0, 0].cpu().numpy()
    wavfile.write(filepath, sampling_rate, audio_data)
    print(f"💾 Music saved to: {filepath}")
    print(f"✅ Music generated on {device} in {time.time() - gen_start_time:.2f} seconds")
    return filepath

def main():
    parser = argparse.ArgumentParser(description="Generate music from a text prompt")
    parser.add_argument("prompt", nargs="?", type=str, help="Text prompt describing the desired music")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    parser.add_argument("--output-dir", type=str, default=DEFAULT_OUTPUT_DIR, help="Directory to save generated music")
    parser.add_argument("--duration", type=int, default=None, help="Duration of music in seconds")
    args = parser.parse_args()
    if not args.prompt:
        print("❌ No prompt provided. Please specify a prompt.")
        print(f"Example: python {os.path.basename(__file__)} 'An upbeat electronic track with a catchy melody'")
        return 1
    filepath = generate_music(
        args.prompt,
        args.output_dir,
        duration=args.duration,
        seed=args.seed
    )
    if filepath:
        print(f"✨ Music generation completed successfully!")
        print_versions()
        try:
            import torch
            if not torch.cuda.is_available() and check_cuda():
                print("\n🔄 NOTE: This music was generated on CPU, but an NVIDIA GPU was detected on the host.")
                print("🔄 If you intended to use GPU, please check the PyTorch and CUDA driver setup within the virtual environment.")
                print(f"🔄 The virtual environment is located at: {VENV_DIR}")
        except ImportError:
            pass
        except Exception as e:
            print(f"Note: Error during post-generation GPU check: {e}")
        return 0
    else:
        print("❌ Music generation failed.")
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
    if not manage_venv_and_execution():
        sys.exit(1)
    sys.exit(main())