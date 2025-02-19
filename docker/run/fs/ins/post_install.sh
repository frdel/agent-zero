#!/bin/bash

# install playwright
bash /ins/install_playwright.sh "$@"

# Cleanup package list
rm -rf /var/lib/apt/lists/*
apt-get clean