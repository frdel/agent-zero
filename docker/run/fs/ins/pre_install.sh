#!/bin/bash

# Update and install necessary packages
apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    nodejs \
    npm \
    openssh-server \
    sudo \
    curl \
    wget \
    git \
    ffmpeg 

# prepare SSH daemon
bash /ins/setup_ssh.sh "$@"