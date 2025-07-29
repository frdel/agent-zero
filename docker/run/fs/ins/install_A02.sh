#!/bin/bash
set -e

# cachebuster script, this helps speed up docker builds

# remove repo (if not local branch)
if [ "$1" != "local" ]; then
    rm -rf /git/agent-zero
fi

# run the original install script again
bash /ins/install_A0.sh "$@"

# remove python packages cache
. "/ins/setup_venv.sh" "$@"
pip cache purge
uv cache prune