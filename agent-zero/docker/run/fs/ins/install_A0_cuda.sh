#!/bin/bash

# branch from parameter
if [ -z "$1" ]; then
    echo "Error: Branch parameter is empty. Please provide a valid branch name."
    exit 1
fi
BRANCH="$1"

# clone project repo branch
git clone -b "$BRANCH" "https://github.com/frdel/agent-zero" "/git/agent-zero"

# setup python environment
. "/ins/setup_venv.sh" "$@"

# Ensure the virtual environment and pip setup
pip install --upgrade pip ipython requests

# Install PyTorch with CUDA support
pip install torch torchvision torchaudio

# Install GPU-enabled FAISS
pip install faiss-gpu

# Install remaining A0 python packages
# Modify requirements.txt to use GPU versions where available
cat /git/agent-zero/requirements.txt | sed 's/faiss-cpu==1.8.0.post1/# faiss-cpu replaced with faiss-gpu above/g' > /tmp/requirements_gpu.txt
pip install -r /tmp/requirements_gpu.txt

# Verify CUDA is available
python -c "import torch; assert torch.cuda.is_available(), 'CUDA is not available'; print('CUDA setup successful, using version:', torch.version.cuda)"

# Preload A0
python /git/agent-zero/preload.py --dockerized=true 