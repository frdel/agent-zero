# Agent Zero with CUDA GPU Support

This directory contains files to build and run Agent Zero with CUDA GPU support, allowing you to leverage NVIDIA GPUs for enhanced performance.

## Prerequisites

1. NVIDIA GPU with CUDA capability
2. NVIDIA driver installed on your host system
3. [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) (nvidia-docker2) installed
4. Docker and Docker Compose installed

## Building the CUDA-enabled Image

To build the CUDA-enabled image, run:

```bash
# On Linux/Mac
bash build-cuda.sh

# On Windows PowerShell
./build-cuda.sh

# Optional: specify a branch
bash build-cuda.sh main  # or any other branch
```

## Running with CUDA Support

There are two ways to run Agent Zero with CUDA support:

### Option 1: Using the CUDA-specific docker-compose file

```bash
# On Linux/Mac
docker-compose -f docker-compose.cuda.yml up -d

# On Windows PowerShell
docker-compose -f docker-compose.cuda.yml up -d
```

### Option 2: Using the start script

```bash
# On Linux/Mac
bash start-cuda.sh

# On Windows PowerShell
./start-cuda.sh
```

## Accessing Agent Zero

Once running, access Agent Zero at: http://localhost:50080

## Stopping Agent Zero

To stop the CUDA version of Agent Zero:

```bash
docker-compose -f docker-compose.cuda.yml down
```

## Switching Between CPU and GPU Versions

To switch between the CPU and GPU versions, stop the currently running version before starting the other:

```bash
# Stop current version (either the regular or CUDA version)
docker-compose down
# or 
docker-compose -f docker-compose.cuda.yml down

# Start the version you want
# For CPU version:
docker-compose up -d

# For GPU version:
docker-compose -f docker-compose.cuda.yml up -d
```

## Notes on Performance

The CUDA-enabled version replaces the CPU-specific packages like `torch` (with the CPU version) and `faiss-cpu` with their GPU-enabled counterparts. This should provide significant performance improvements for operations that can leverage GPU acceleration. 