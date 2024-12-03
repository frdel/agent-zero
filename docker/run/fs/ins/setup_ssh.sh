#!/bin/bash

# Set up SSH
mkdir /var/run/sshd && \
    # echo 'root:toor' | chpasswd && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config