#!/bin/bash

sudo -H apt-get install -y \
    python3-dev python3-babel python3-venv \
    uwsgi uwsgi-plugin-python3 \
    git build-essential libxslt-dev zlib1g-dev libffi-dev libssl-dev

sudo -H useradd --shell /bin/bash --system \
    --home-dir "/usr/local/searxng" \
    --comment 'Privacy-respecting metasearch engine' \
    searxng

sudo -H mkdir "/usr/local/searxng"
sudo -H chown -R "searxng:searxng" "/usr/local/searxng"

# Start a new shell from new created user and clone SearXNG:
sudo -H -u searxng -i bash /ins/install_searxng2.sh
