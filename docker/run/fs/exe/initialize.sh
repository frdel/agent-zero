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
apt-get update > /dev/null 2>&1 &

# Start SSH service in background
/usr/sbin/sshd -D &

# Start searxng server in background
su - searxng -c "bash /exe/run_searxng.sh \"$@\"" &

# Start A0 and restart on exit
bash /exe/run_A0.sh "$@"
if [ $? -ne 0 ]; then
    echo "A0 script exited with an error. Restarting container..."
    exit 1
fi