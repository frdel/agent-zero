#!/bin/bash
set -e

apt-get update && apt-get install -y wget

wget -qO- https://pascalroeleven.nl/deb-pascalroeleven.gpg | tee /etc/apt/keyrings/deb-pascalroeleven.gpg

echo \
  "deb [arch=amd64 signed-by=/etc/apt/keyrings/deb-pascalroeleven.gpg] http://deb.pascalroeleven.nl/python3.12 bookworm-backports main" \
  > /etc/apt/sources.list.d/pascalroeleven.list

# Update and install necessary packages
apt-get update && apt-get install -y \
    -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" \
    python3.12 \
    python3.12-venv \
    nodejs \
    npm \
    openssh-server \
    sudo \
    curl \
    git \
    ffmpeg 

# Install npx and shx for installing/executing MCP servers
npm i -g npx shx

update-alternatives --install /usr/bin/python python /usr/bin/python3.12 1
update-alternatives --set python /usr/bin/python3.12

wget -qO- https://bootstrap.pypa.io/get-pip.py > /tmp/get-pip.py && \
  python /tmp/get-pip.py --force --break-system-packages && \
  rm /tmp/get-pip.py

python -m pip config set global.break-system-packages true

pip install -U pip setuptools virtualenv

# Prepare SSH daemon
bash /ins/setup_ssh.sh "$@"
