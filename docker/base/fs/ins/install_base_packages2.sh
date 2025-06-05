#!/bin/bash
set -e

echo "====================BASE PACKAGES2 START===================="


apt-get install -y --no-install-recommends \
    openssh-server ffmpeg supervisor

echo "====================BASE PACKAGES2 END===================="
