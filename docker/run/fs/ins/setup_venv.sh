#!/bin/bash
set -e

# this has to be ready from base image
# if [ ! -d /opt/venv ]; then
#     # Create and activate Python virtual environment
#     python3.12 -m venv /opt/venv
#     source /opt/venv/bin/activate
# else
    source /opt/venv/bin/activate
# fi