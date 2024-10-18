#!/bin/bash

# Copy all contents from /fs to root directory (/) with overwriting
cp -r /fs/* / --no-preserve=ownership,mode

# allow execution of /root/.bashrc and /root/.profile
chmod 444 /root/.bashrc
chmod 444 /root/.profile

# update package list to save time later
apt-get update

# Start SSH service
exec /usr/sbin/sshd -D