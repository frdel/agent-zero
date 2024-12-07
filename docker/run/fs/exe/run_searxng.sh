#!/bin/bash

# start webapp
sudo -H -u searxng -i
cd /usr/local/searxng/searxng-src
export SEARXNG_SETTINGS_PATH="/etc/searxng/settings.yml"
python searx/webapp.py