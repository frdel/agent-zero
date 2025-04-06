#!/bin/bash

if [ ! -d /opt/venv ]; then
    # Create and activate Python virtual environment
    python3 -m venv /opt/venv
    source /opt/venv/bin/activate
else
    source /opt/venv/bin/activate
fi