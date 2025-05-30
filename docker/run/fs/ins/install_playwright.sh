#!/bin/bash

# activate venv
. "/ins/setup_venv.sh" "$@"

# install playwright if not installed (should be from requirements.txt)
pip install playwright

# install chromium with dependencies
# for kali-based
# if [ "$@" = "hacking" ]; then
    apt-get install -y fonts-unifont libnss3 libnspr4 libatk1.0-0 libatspi2.0-0 libxcomposite1 libxdamage1 libatk-bridge2.0-0    
    playwright install chromium-headless-shell
# else
#     # for debian based
#     playwright install --with-deps chromium-headless-shell
# fi

