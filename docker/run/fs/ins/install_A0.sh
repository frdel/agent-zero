#!/bin/bash
set -e

# Exit immediately if a command exits with a non-zero status.
# set -e

# branch from parameter
if [ -z "$1" ]; then
    echo "Error: Branch parameter is empty. Please provide a valid branch name."
    exit 1
fi
BRANCH="$1"

git clone -b "$BRANCH" "https://github.com/frdel/agent-zero" "/git/agent-zero" || {
    echo "CRITICAL ERROR: Failed to clone repository. Branch: $BRANCH"
    exit 1
}

. "/ins/setup_venv.sh" "$@"

# moved to base image
# # Ensure the virtual environment and pip setup
# pip install --upgrade pip ipython requests
# # Install some packages in specific variants
# pip install torch --index-url https://download.pytorch.org/whl/cpu

uv pip install -v mcp==1.3.0 || {
    echo "ERROR: Failed during separate attempt to install mcp==1.3.0. Will proceed to full requirements.txt install anyway."
}
python -c "import mcp; from mcp import ClientSession; print(f'DEBUG: mcp and mcp.ClientSession imported successfully after separate install. mcp path: {mcp.__file__}')" || {
    echo "ERROR: mcp package or mcp.ClientSession NOT importable after separate mcp==1.3.0 installation attempt. Full requirements.txt will run next."
}

# Install remaining A0 python packages
uv pip install -r /git/agent-zero/requirements.txt

uv pip install langchain-anthropic==0.3.15 # TODO: remove after browser-use update

python -c "import mcp; from mcp import ClientSession; print(f'DEBUG: mcp and mcp.ClientSession imported successfully after requirements.txt. mcp path: {mcp.__file__}')" || {
    echo "CRITICAL ERROR: mcp package or mcp.ClientSession not found or failed to import after requirements.txt processing."
}

# install playwright
bash /ins/install_playwright.sh "$@"

# Preload A0
python /git/agent-zero/preload.py --dockerized=true
