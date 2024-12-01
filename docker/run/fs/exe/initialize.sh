#!/bin/bash

# branch from parameter
if [ -z "$1" ]; then
    echo "Error: Branch parameter is empty. Please provide a valid branch name."
    exit 1
fi
BRANCH="$1"

# Copy all contents from persistent /per to root directory (/) without overwriting
cp -r --no-preserve=ownership,mode /per/* /

# allow execution of /root/.bashrc and /root/.profile
chmod 444 /root/.bashrc
chmod 444 /root/.profile

# update package list to save time later
apt-get update &

# Start SSH service in background
if [ "$BRANCH" != "development" ]; then
    /usr/sbin/sshd -D -o ListenAddress=127.0.0.1 &
else
    /usr/sbin/sshd -D &
fi

# Start searxng server in background
sudo -H -u searxng -i bash /exe/run_searxng.sh &

# Start A0 and restart on exit
bash /exe/run_A0.sh
if [ $? -ne 0 ]; then
    echo "A0 script exited with an error. Restarting container..."
    exit 1
fi