#!/bin/bash

# Copy all contents from /fs to root directory (/) without overwriting
cp -rn --no-preserve=ownership,mode /fs/* /

# allow execution of /root/.bashrc and /root/.profile
chmod 444 /root/.bashrc
chmod 444 /root/.profile

# update package list to save time later
apt-get update

# Start SSH service in background
/usr/sbin/sshd -D &

# Start A0 and restart on exit
bash /exe/run_A0.sh
if [ $? -ne 0 ]; then
    echo "A0 script exited with an error. Restarting container..."
    exit 1
fi