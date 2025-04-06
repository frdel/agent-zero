#!/bin/bash

echo "==== Starting Image Generation Script ===="

# Display NVIDIA GPU information if available
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
    echo "⚠️ Warning: nvidia-smi not found. GPU acceleration may not be available."
fi

# Set environment variables to force CUDA
export CUDA_VISIBLE_DEVICES=0
export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:128

# Ensure the Python runtime can find CUDA
echo "====== CUDA Environment Variables ======"
echo "CUDA_VISIBLE_DEVICES: $CUDA_VISIBLE_DEVICES"
echo "LD_LIBRARY_PATH: $LD_LIBRARY_PATH"

# Execute Python script
echo "====== Running Image Generation ======"
python /a0/instruments/custom/image_generation/image_generation.py "$@"

# Check exit status
if [ $? -eq 0 ]; then
    echo "✅ Image generation completed successfully"
else
    echo "❌ Image generation failed with error code $?"
fi 