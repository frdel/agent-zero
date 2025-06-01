#!/bin/bash
set -e

echo "====================BASE PACKAGES START===================="

apt-get install -y --no-install-recommends \
    nodejs npm openssh-server sudo curl wget git ffmpeg supervisor cron tesseract-ocr-all poppler-utils

echo "====================BASE PACKAGES NPM===================="

npm i -g npx shx

echo "====================BASE PACKAGES END===================="
