#!/bin/bash
set -e

# Set up SSH
mkdir -p /var/run/sshd && \
    # echo 'root:toor' | chpasswd && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config