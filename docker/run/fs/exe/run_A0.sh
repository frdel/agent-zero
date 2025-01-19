#!/bin/bash

# Loop to restart the Python script when it finishes
while true; do

    . "/ins/setup_venv.sh" "$@"
    . "/ins/copy_A0.sh" "$@"

    python /a0/prepare.py --dockerized=true
    python /a0/preload.py --dockerized=true

    echo "Starting A0..."
    python /a0/run_ui.py \
        --dockerized=true \
        --port=80 \
        --host="0.0.0.0" \
        --code_exec_docker_enabled=false \
        --code_exec_ssh_enabled=true \
        # --code_exec_ssh_addr="localhost" \
        # --code_exec_ssh_port=22 \
        # --code_exec_ssh_user="root" \
        # --code_exec_ssh_pass="toor"
    
    # Check the exit status
    if [ $? -ne 0 ]; then
        echo "A0 script exited with an error. Restarting..."
    else
        echo "A0 script finished. Restarting..."
    fi

    # Optional: Add a small delay if needed to avoid rapid restarts
    sleep 1
done
