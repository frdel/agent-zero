#!/bin/bash
set -x  # This will print each command before executing it

# Ensure .bashrc is in the root directory
if [ ! -f /root/.bashrc ]; then
    cp /etc/skel/.bashrc /root/.bashrc
    chmod 444 /root/.bashrc
fi

# Ensure .profile is in the root directory
if [ ! -f /root/.profile ]; then
    cp /etc/skel/.bashrc /root/.profile
    chmod 444 /root/.profile
fi

# Add the command to change directory upon login
if ! grep -Fxq "cd /home/agent-zero/work_dir" /root/.bashrc; then
    echo "cd /home/agent-zero/work_dir" >> /root/.bashrc
fi

echo "cd /home/agent-zero/work_dir" >> /home/agent-zero/.bashrc

apt-get update

# Start SSH service
exec /usr/sbin/sshd -D
