#!/bin/bash

# fix permissions for cron files
chmod 0644 /etc/cron.d/*

echo "=====BEFORE UPDATE====="

# Set DEBIAN_FRONTEND to noninteractive to prevent prompts
export DEBIAN_FRONTEND=noninteractive

# Update and install necessary packages
apt clean
apt-get update && apt-get upgrade -y && apt-get -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" install -y \
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
    nginx \
    supervisor \
    cron \
    libmagic-dev \
    poppler-utils \
    tesseract-ocr \
    qpdf \
    libreoffice \
    pandoc \
    libgtk-3-0 \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libasound2 \
    libasound2-data \
    cargo

echo "=====MID UPDATE====="

# for some reason npm crashes builds on amd64 in this version and has to be installed separately
# A0 can install it when needed
# The line below is now redundant as npm is included in the main install list above
# apt-get install -y \
#     npm 

echo "=====AFTER UPDATE====="

# # Configure system alternatives so that /usr/bin/python3 points to Python 3.12
# sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1
# sudo update-alternatives --set python3 /usr/bin/python3.12

# Update pip3 symlink: if pip3.12 exists, point pip3 to it;
# otherwise, install pip using Python 3.12's ensurepip.
# if [ -f /usr/bin/pip3.12 ]; then
#   sudo ln -sf /usr/bin/pip3.12 /usr/bin/pip3
# else
#   python3 -m ensurepip --upgrade
#   python3 -m pip install --upgrade pip
# fi

# Install npx for use by local MCP Servers
echo "DEBUG: Installing npx and shx globally using npm..."
npm i -g npx shx || {
    echo "CRITICAL ERROR: Failed to install npx and shx using npm."
    # exit 1 # Optionally exit if this is critical enough
}
echo "DEBUG: npx and shx installation attempt finished."


# Prepare SSH daemon
bash /ins/setup_ssh.sh "$@"
