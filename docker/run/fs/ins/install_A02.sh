#!/bin/bash
set -e

# cachebuster script, this helps speed up docker builds

# remove repo
rm -rf /git/agent-zero

# run the original install script again
bash /ins/install_A0.sh "$@"

# remove python packages cache
. "/ins/setup_venv.sh" "$@"
pip cache purge
uv cache prune