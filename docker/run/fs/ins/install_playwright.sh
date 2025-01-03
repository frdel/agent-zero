#!/bin/bash

# activate venv
. "/ins/setup_venv.sh" "$@"

# install playwright
pip install playwright

# install chromium with dependencies
playwright install --with-deps chromium
