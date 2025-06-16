#!/bin/bash
# This launcher script explicitly defines all necessary paths to ensure
# the Conda environment is used correctly, even when this script is run with sudo.

# --- Define Paths (Verify these if your install is non-standard) ---
CONDA_ENV_PATH="/home/natefoxtrot/miniconda3/envs/a0_hacking"
PYTHON_EXEC="${CONDA_ENV_PATH}/bin/python"

# This path is based on tracebacks showing Python 3.12. Please verify if your version differs.
SITE_PACKAGES_PATH="${CONDA_ENV_PATH}/lib/python3.12/site-packages"

# --- Set the PYTHONPATH Environment Variable ---
# This explicitly tells the Python interpreter where to find its installed packages.
export PYTHONPATH="${SITE_PACKAGES_PATH}"

echo "Starting Agent-Zero..."
echo "Interpreter: $PYTHON_EXEC"
echo "Package Path (PYTHONPATH): $PYTHONPATH"

# --- Execute the script ---
# Since this entire script is run with 'sudo', this command will run as root,
# but it will use the correct Python interpreter and know where its packages are.
$PYTHON_EXEC run_ui.py
