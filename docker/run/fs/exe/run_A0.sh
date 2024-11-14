#!/bin/bash

# Paths
PYTHON_SCRIPT="/a0/run_ui.py"
SOURCE_DIR="/git/agent-zero"
TARGET_DIR="/a0"


# Loop to restart the Python script when it finishes
while true; do

    # Create virtual environment if it doesn't exist
    if [ ! -d /opt/venv ]; then
        echo "Creating virtual environment..."
        python3 -m venv /opt/venv
        /opt/venv/bin/pip install ipython requests
    fi

    # Activate the virtual environment
    source /opt/venv/bin/activate

    # Copy repository files if target is empty
    if [ -z "$(ls -A "$TARGET_DIR")" ]; then
        echo "Copying files from $SOURCE_DIR to $TARGET_DIR..."
        cp -rn --no-preserve=ownership,mode "$SOURCE_DIR/." "$TARGET_DIR"
    fi

    echo "Starting A0..."
    python "$PYTHON_SCRIPT" --port 80 --host "0.0.0.0"
    
    # Check the exit status
    if [ $? -ne 0 ]; then
        echo "A0 script exited with an error. Restarting..."
    else
        echo "A0 script finished. Restarting..."
    fi

    # Optional: Add a small delay if needed to avoid rapid restarts
    sleep 1
done
