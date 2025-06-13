#!/bin/bash

# fix permissions for cron files
chmod 0644 /etc/cron.d/*

# Prepare SSH daemon
bash /ins/setup_ssh.sh "$@"
