#!/bin/bash

# activate venv
. "/ins/setup_venv.sh" "$@"

# install playwright if not installed
pip install playwright

# install chromium with dependencies
playwright install --with-deps chromium-headless-shell
