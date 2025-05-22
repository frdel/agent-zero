#!/bin/bash
set -e

# fix permissions for cron files if directory exists
if [ -d "/etc/cron.d" ] && [ "$(ls -A /etc/cron.d)" ]; then
    chmod 0644 /etc/cron.d/*
fi

echo "=====BEFORE UPDATE====="

apt clean

# ★ 1. Add sid repo & pin it
echo "deb http://deb.debian.org/debian sid main" > /etc/apt/sources.list.d/debian-sid.list
cat >/etc/apt/preferences.d/python312 <<'EOF'
Package: *
Pin: release a=sid
Pin-Priority: 100

Package: python3.12*
Pin: release a=sid
Pin-Priority: 990
EOF

apt-get update && apt-get -y upgrade

apt-get install -y --no-install-recommends \
    python3.12 python3.12-venv python3.12-dev

echo "=====MID UPDATE====="

# ★ 2. Refresh & install everything we need, including python3.12

apt-get install -y --no-install-recommends \
    nodejs openssh-server sudo curl wget git ffmpeg supervisor cron

echo "=====AFTER UPDATE====="

# ★ 3. Switch the interpreter
update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.13 0
update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1
update-alternatives --set python3 /usr/bin/python3.12

# ★ 4. Make sure pip matches
# python3 -m ensurepip --upgrade
# python3 -m pip install --upgrade pip

# Prepare SSH daemon
bash /ins/setup_ssh.sh "$@"
