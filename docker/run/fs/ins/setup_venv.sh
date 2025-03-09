#!/bin/bash

if [ ! -d /opt/venv ]; then
    # Create and activate Python virtual environment
    set -e
    python3 -m venv /opt/venv
    source /opt/venv/bin/activate
else
    set -e
    source /opt/venv/bin/activate
fi
