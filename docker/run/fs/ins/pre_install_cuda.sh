#!/bin/bash

# Set non-interactive frontend to avoid prompts
export DEBIAN_FRONTEND=noninteractive
export TZ=Etc/UTC

# Update and install necessary packages for Ubuntu-based CUDA image
apt-get update && apt-get install -y \
    python3 \
    python3-venv \
    python3-pip \
    nodejs \
    npm \
    openssh-server \
    sudo \
    curl \
    wget \
    git \
    ffmpeg \
    software-properties-common \
    tzdata

# Set timezone non-interactively
ln -fs /usr/share/zoneinfo/Etc/UTC /etc/localtime
dpkg-reconfigure --frontend noninteractive tzdata

# Add deadsnakes PPA to get Python 3.12 non-interactively
DEBIAN_FRONTEND=noninteractive add-apt-repository -y ppa:deadsnakes/ppa && \
apt-get update && \
DEBIAN_FRONTEND=noninteractive apt-get install -y python3.12 python3.12-venv python3.12-dev

# Configure system alternatives so that /usr/bin/python3 points to Python 3.12
update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1
update-alternatives --set python3 /usr/bin/python3.12

# Update pip3 symlink: if pip3.12 exists, point pip3 to it;
# otherwise, install pip using Python 3.12's ensurepip.
if [ -f /usr/bin/pip3.12 ]; then
  ln -sf /usr/bin/pip3.12 /usr/bin/pip3
else
  python3 -m ensurepip --upgrade
  python3 -m pip install --upgrade pip
fi

# Prepare SSH daemon
bash /ins/setup_ssh.sh "$@" 