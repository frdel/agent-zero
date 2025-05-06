#!/bin/bash

# fix permissions for cron files
chmod 0644 /etc/cron.d/*

echo "=====BEFORE UPDATE====="

# Update and install necessary packages
apt clean
apt-get update && apt-get upgrade -y && apt-get install -y \
    python3 \
    python3-venv \
    python3-pip \
    nodejs \
    openssh-server \
    sudo \
    curl \
    wget \
    git \
    ffmpeg \
    supervisor \
    cron

echo "=====MID UPDATE====="

# for some reason npm crashes builds on amd64 in this version and has to be installed separately
# A0 can install it when needed
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

# Prepare SSH daemon
bash /ins/setup_ssh.sh "$@"
