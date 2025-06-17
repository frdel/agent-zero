#!/bin/bash
set -e

echo "====================BASE PACKAGES4 START===================="

apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-script-latn poppler-utils

echo "====================BASE PACKAGES4 END===================="