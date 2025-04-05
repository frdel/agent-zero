#!/bin/bash

# Update and install necessary packages
apt-get update && apt-get install -y \
    python3 \
    python3-venv \
    nodejs \
    npm \
    openssh-server \
    sudo \
    curl \
    wget \
    git \
    ffmpeg 

# # Configure system alternatives so that /usr/bin/python3 points to Python 3.12
# sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1
# sudo update-alternatives --set python3 /usr/bin/python3.12

# Update pip3 symlink: if pip3.12 exists, point pip3 to it;
# otherwise, install pip using Python 3.12's ensurepip.
# if [ -f /usr/bin/pip3.12 ]; then
#   sudo ln -sf /usr/bin/pip3.12 /usr/bin/pip3
# else
  python3 -m ensurepip --upgrade
  python3 -m pip install --upgrade pip
# fi

# Prepare SSH daemon
bash /ins/setup_ssh.sh "$@"
