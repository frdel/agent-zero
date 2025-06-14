#!/bin/bash

# install playwright - moved to install A0
# bash /ins/install_playwright.sh "$@"

# searxng - moved to base image
# bash /ins/install_searxng.sh "$@"

#TODO : move to base image

apt-get install -y --no-install-recommends \
    tesseract-ocr-all poppler-utils