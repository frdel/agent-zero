#!/bin/bash
set -e

echo "====================BASE PACKAGES START===================="

apt-get install -y --no-install-recommends \
    nodejs npm openssh-server sudo curl wget git ffmpeg supervisor cron

echo "====================BASE PACKAGES END===================="
