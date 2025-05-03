#!/bin/bash

# start webapp
cd /usr/local/searxng/searxng-src
export SEARXNG_SETTINGS_PATH="/etc/searxng/settings.yml"

# activate venv
source "/usr/local/searxng/searx-pyenv/bin/activate"

exec python /usr/local/searxng/searxng-src/searx/webapp.py
