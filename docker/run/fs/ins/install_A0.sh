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

# Install some packages in specific variants
pip install torch --index-url https://download.pytorch.org/whl/cpu

# Install remaining A0 python packages
pip install -r /git/agent-zero/requirements.txt

# install playwright
bash /ins/install_playwright.sh "$@"

# Preload A0
python /git/agent-zero/preload.py --dockerized=true