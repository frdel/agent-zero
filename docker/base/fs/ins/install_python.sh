#!/bin/bash
set -e

echo "====================PYTHON START===================="

echo "====================PYTHON 3.12 & SID REPO===================="

apt clean

# ★ 1. Add sid repo & pin it for python 3.12
echo "deb http://deb.debian.org/debian sid main" > /etc/apt/sources.list.d/debian-sid.list
cat >/etc/apt/preferences.d/python312 <<'EOF'
Package: *
Pin: release a=sid
Pin-Priority: 100

Package: python3.12*
Pin: release a=sid
Pin-Priority: 990

# Prevent Python 3.13 from being installed
Package: python3.13*
Pin: release *
Pin-Priority: -1
EOF

apt-get update && apt-get -y upgrade

apt-get install -y --no-install-recommends \
    python3.12 python3.12-venv python3.12-dev

# ★ 3. Switch the interpreter
# update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.13 0
# update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1
# update-alternatives --set python3 /usr/bin/python3.12

echo "====================PYTHON VERSION: $(python3 --version) ===================="
echo "====================PYTHON OTHERS: $(ls /usr/bin/python*) "

echo "====================PYTHON VENV===================="

# create and activate default venv
python3.12 -m venv /opt/venv
source /opt/venv/bin/activate

# upgrade pip and install static packages
pip install --no-cache-dir --upgrade pip ipython requests
# Install some packages in specific variants
pip install --no-cache-dir \
    torch==2.4.0 \
    torchvision==0.19.0 \
    --index-url https://download.pytorch.org/whl/cpu

echo "====================PYTHON UV ===================="

curl -Ls https://astral.sh/uv/install.sh | UV_INSTALL_DIR=/usr/local/bin sh

# clean up pip cache
pip cache purge

echo "====================PYTHON END===================="
