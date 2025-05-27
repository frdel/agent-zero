#!/bin/bash
set -e

echo "=====BASE PACKAGES====="

# Hold python3 packages to prevent overrides
apt-mark hold python3

# Install with --no-install-recommends to minimize unwanted dependencies
apt-get install -y --no-install-recommends \
    nodejs openssh-server sudo curl wget git ffmpeg supervisor cron


echo "=====AFTER UPDATE====="


echo "=====PYTHON VERSION: $(python3 --version) ====="
echo "=====PYTHON OTHERS: $(ls /usr/bin/python*) ====="
sleep 10