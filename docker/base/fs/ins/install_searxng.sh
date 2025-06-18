#!/bin/bash
set -e

echo "====================SEARXNG1 START===================="

# Install necessary packages
apt-get install -y \
    python3.12-dev python3.12-venv \
    git build-essential libxslt-dev zlib1g-dev libffi-dev libssl-dev
#    python3.12-babel uwsgi uwsgi-plugin-python3


# Add the searxng system user
useradd --shell /bin/bash --system \
    --home-dir "/usr/local/searxng" \
    --comment 'Privacy-respecting metasearch engine' \
    searxng

# Add the searxng user to the sudo group
usermod -aG sudo searxng

# Create the searxng directory and set ownership
mkdir "/usr/local/searxng"
chown -R "searxng:searxng" "/usr/local/searxng"

echo "====================SEARXNG1 END===================="

# Start a new shell as the searxng user and run the installation script
su - searxng -c "bash /ins/install_searxng2.sh"

