#!/bin/bash

VENV_DIR="/opt/instruments_venv"
VENV_PY="$VENV_DIR/bin/python"

echo "==== Starting Sound Effects Generation Script ===="

# Install system dependencies for soundfile
echo "🔄 Installing system dependencies for soundfile..."
apt-get update && apt-get install -y libsndfile1 || {
    echo "⚠️ Failed to install libsndfile1. Trying alternative package name..."
    apt-get install -y libsndfile1-dev || {
        echo "❌ Failed to install soundfile system dependencies. Sound generation may not work properly."
    }
}

# Show GPU info if available
if command -v nvidia-smi &> /dev/null; then
    echo "✅ NVIDIA GPU detected, displaying information:"
    nvidia-smi
    
    # Get CUDA version
    if [ -x "$(command -v nvcc)" ]; then
        echo "✅ NVCC (CUDA Compiler) found:"
        nvcc --version
    else
        echo "⚠️ NVCC not found, CUDA development tools may not be installed properly"
    fi
    
    # Check CUDA libraries
    echo "Checking CUDA libraries:"
    if ldconfig -p | grep -q libcuda.so; then
        echo "✅ CUDA libraries found in system path"
        ldconfig -p | grep libcuda.so
    else
        echo "⚠️ CUDA libraries not found in system path"
    fi
else
    echo "⚠️ No NVIDIA GPU detected (nvidia-smi not found)."
fi

# Set CUDA env vars if desired
export CUDA_VISIBLE_DEVICES=0
export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:128

# If venv Python does not exist, create venv and install CPU deps
if [ ! -x "$VENV_PY" ]; then
    echo "🛠️ venv not found, creating at $VENV_DIR and installing dependencies..."
    python3 -m venv "$VENV_DIR"
    "$VENV_PY" -m pip install --upgrade pip setuptools wheel
    "$VENV_PY" -m pip install \
        torch==2.6.0 torchvision torchaudio \
        transformers==4.38.2 \
        diffusers accelerate \
        numpy>=1.21.0 scipy>=1.7.0 soundfile>=0.10.3
    echo "✅ venv created and dependencies installed."
else
    # Ensure all dependencies are installed in existing venv
    echo "🔄 Verifying dependencies in venv..."
    "$VENV_PY" -m pip install --upgrade \
        torch==2.6.0 torchvision torchaudio \
        transformers==4.38.2 \
        diffusers accelerate \
        numpy>=1.21.0 scipy>=1.7.0 soundfile>=0.10.3 || {
        echo "❌ Failed to install/upgrade dependencies in venv"
        exit 1
    }
fi

# Verify soundfile installation
echo "🔍 Verifying soundfile installation..."
"$VENV_PY" -c "import soundfile; print(f'✅ soundfile version: {soundfile.__version__}')" || {
    echo "❌ soundfile import failed. Please check the installation."
    exit 1
}

# Ensure the Python runtime can find CUDA
echo "====== CUDA Environment Variables ======"
echo "CUDA_VISIBLE_DEVICES: $CUDA_VISIBLE_DEVICES"
echo "LD_LIBRARY_PATH: $LD_LIBRARY_PATH"

echo "====== Running Sound Effects Generation ======"

# Start the Python process in the background
"$VENV_PY" /a0/instruments/default/sound_effects/sound_effects.py "$@" &
PY_PID=$!

# Heartbeat loop
while kill -0 $PY_PID 2>/dev/null; do
    sleep 9
    if kill -0 $PY_PID 2>/dev/null; then
        echo "⏳ Process still running. Monitor terminal for output."
    fi
done

wait $PY_PID
status=$?

if [ $status -eq 0 ]; then
    echo "✅ Sound effects generation completed successfully"
else
    echo "❌ Sound effects generation failed with error code $status"
fi 