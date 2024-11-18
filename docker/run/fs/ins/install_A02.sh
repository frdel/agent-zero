#!/bin/bash

# cachebuster script, this helps speed up docker builds
rm -rf /github/agent-zero

# run the original install script again
bash /ins/install_A0.sh

# remove python packages cache
source /opt/venv/bin/activate
pip cache purge