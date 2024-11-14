#!/bin/bash

# Copy all contents from /fs to root directory (/) without overwriting
cp -rn --no-preserve=ownership,mode /fs/* /

# allow execution of /root/.bashrc and /root/.profile
chmod 444 /root/.bashrc
chmod 444 /root/.profile

# update package list to save time later
apt-get update

# Start A0
bash /exe/run_A0.sh

# Start SSH service
exec /usr/sbin/sshd -D