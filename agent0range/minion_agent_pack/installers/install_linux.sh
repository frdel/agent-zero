#!/bin/bash
mkdir -p ~/.local/bin ~/.config/systemd/user
cp minion.py ~/.local/bin/.minion
chmod +x ~/.local/bin/.minion
cat <<EOL > ~/.config/systemd/user/minion.service
[Unit]
Description=Agent Zero Minion
[Service]
ExecStart=/usr/bin/python3 ~/.local/bin/.minion
Restart=always
[Install]
WantedBy=default.target
EOL
systemctl --user daemon-reload
systemctl --user enable minion.service --now
