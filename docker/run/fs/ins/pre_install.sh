#!/bin/bash
set -e

# update apt
apt-get update

# fix permissions for cron files if any
if [ -f /etc/cron.d/* ]; then
    chmod 0644 /etc/cron.d/*
fi

# Prepare SSH daemon
bash /ins/setup_ssh.sh "$@"
