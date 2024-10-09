#!/bin/bash

USER_HOME="/home/user"

if [ ! -f "$USER_HOME/.bashrc" ]; then # Adjusted path here!
    cp /etc/skel/.bashrc "$USER_HOME/.bashrc"
fi

if [ ! -f "$USER_HOME/.profile" ]; then # Adjusted path here!
     cp "/etc/skel/.bashrc" "$USER_HOME/.profile"
fi
    
apt-get update
  
exec /usr/sbin/sshd -D  # Start SSH service.
