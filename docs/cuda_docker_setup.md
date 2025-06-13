# Agent Zero: CUDA GPU Support 🚀

This guide explains how to build and run Agent Zero with NVIDIA GPU acceleration using CUDA. Running with CUDA enables faster performance for AI workloads by leveraging your GPU.

---

## Prerequisites

Before you begin, ensure you have:

1. **NVIDIA GPU** with CUDA capability
2. **NVIDIA Driver** installed on your host system
3. **NVIDIA Container Toolkit** ([Install Guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html))  
   _This enables Docker to access your GPU_
4. **Docker** and **Docker Compose** installed

---

## 1. Build the CUDA Docker Image

Open a terminal in this directory and run:

```bash
# Set the branch you want to build from (default: main)
$branch="main"
docker build --no-cache -t frdel/agent-zero-run-cuda:testing --build-arg BRANCH=$branch -f Dockerfile.cuda .
```

---

## 2. Run Agent Zero with CUDA Support

You can start Agent Zero with GPU support using Docker Compose:

```bash
# On Linux, macOS, or Windows PowerShell:
docker-compose -f docker-compose.cuda.yml up -d
```

- This will launch Agent Zero in the background with GPU acceleration enabled.

---

## 3. Access Agent Zero

Once the container is running, open your browser and go to:

[http://localhost:50080](http://localhost:50080)

---

## 4. Stopping Agent Zero

To stop the CUDA-enabled Agent Zero container:

```bash
docker-compose -f docker-compose.cuda.yml down
```

---

## 5. Switching Between CPU and GPU Versions

You can easily switch between the CPU and GPU versions:

1. **Stop the currently running version:**
   ```bash
   # For CPU version:
   docker-compose down
   # For GPU version:
   docker-compose -f docker-compose.cuda.yml down
   ```

2. **Start the version you want:**
   ```bash
   # CPU version:
   docker-compose -f docker-compose.yml up -d

   # GPU (CUDA) version:
   docker-compose -f docker-compose.cuda.yml up -d
   ```

---

## Troubleshooting & Tips

- **First time setup may take several minutes** as dependencies are downloaded and installed.
- If you encounter issues with GPU access, verify your NVIDIA drivers and the NVIDIA Container Toolkit are correctly installed.
- To check if CUDA is available inside the container, you can run:
  ```bash
  docker exec -it <container_name> python3 -c "import torch; print(torch.cuda.is_available())"
  ```
- For advanced configuration, see the comments in [`Dockerfile.cuda`](mdc:docker/run/Dockerfile.cuda).

---

## More Information

- [NVIDIA Container Toolkit Documentation](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
- [Agent Zero Project](https://github.com/frdel/agent-zero) (replace with your actual repo link if different)

---

**Enjoy accelerated AI with Agent Zero and CUDA!**
