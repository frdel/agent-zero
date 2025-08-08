#!/bin/bash
set -e

apt-get install -y --no-install-recommends redis-server

# install playwright - moved to install A0
# bash /ins/install_playwright.sh "$@"

# searxng - moved to base image
# bash /ins/install_searxng.sh "$@"
