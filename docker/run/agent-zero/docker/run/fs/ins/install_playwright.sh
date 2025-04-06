#!/bin/bash

# activate venv
. "/ins/setup_venv.sh" "$@"

# install playwright if not installed
pip install playwright

# install chromium with dependencies
# for kali-based
if [ "$@" = "hacking" ]; then
    apt-get install -y fonts-unifont libnss3 libnspr4
    playwright install chromium-headless-shell
else
    # for debian based
    playwright install --with-deps chromium-headless-shell
fi

