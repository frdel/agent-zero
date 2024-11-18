#!/bin/bash

BRANCH="development"

git clone -b "$BRANCH" "https://github.com/frdel/agent-zero" "/git/agent-zero"

# Create and activate Python virtual environment
python3 -m venv /opt/venv
source /opt/venv/bin/activate

# Ensure the virtual environment and pip setup
pip install --upgrade pip ipython requests

# Install some packages in specific variants
pip install torch --index-url https://download.pytorch.org/whl/cpu

# Install remaining A0 python packages
pip install -r /github/agent-zero/requirements.txt

# Preload A0
python /github/agent-zero/preload.py
