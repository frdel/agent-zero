#!/bin/bash

set -e

# 1. Remove conda environment if it exists
echo "Removing conda environment 'az-bundle' if it exists..."
conda env remove -n az-bundle -y || echo "Conda environment 'az-bundle' does not exist."

# 2. Create new environment with Python 3.12 and activate it
echo "Creating new conda environment 'az-bundle' with Python 3.12..."
conda create -n az-bundle python=3.12 -y
if [ $? -ne 0 ]; then
    echo "Error creating conda environment."
    exit 1
fi

echo "Activating conda environment 'az-bundle'..."
source $(conda info --base)/etc/profile.d/conda.sh
conda activate az-bundle
if [ $? -ne 0 ]; then
    echo "Error activating conda environment."
    exit 1
fi

# 3. Purge folder ./agent-zero (retry mechanism in case of failure)
if [ -d "agent-zero" ]; then
    echo "Deleting agent-zero folder..."
    rm -rf agent-zero
    if [ -d "agent-zero" ]; then
        echo "Error: Unable to delete agent-zero folder, retrying..."
        sleep 3
        rm -rf agent-zero
    fi
    if [ -d "agent-zero" ]; then
        echo "Error: Failed to purge agent-zero folder after retry."
        exit 1
    fi
fi

# 4. Clone the repository (development branch)
echo "Cloning the repository (development branch)..."
git clone --branch development https://github.com/frdel/agent-zero agent-zero
if [ $? -ne 0 ]; then
    echo "Error cloning the repository."
    exit 1
fi

# 5. Change directory to agent-zero
cd agent-zero || { echo "Error changing directory"; exit 1; }

# 6. Install requirements
echo "Installing requirements from requirements.txt..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Error installing requirements."
    exit 1
fi

# 7. Install specific version of pefile
# skip

# 8. Run bundle.py
echo "Running bundle.py..."
python ./bundle/bundle.py
if [ $? -ne 0 ]; then
    echo "Error running bundle.py."
    exit 1
fi

# # 9. Move the generated 7z file to the script directory and remove agent-zero folder
# BUNDLE_FILE="bundle/dist/agent-zero.7z"
# if [ -f "$BUNDLE_FILE" ]; then
#     SCRIPT_DIR=$(dirname "$0")
#     echo "Moving $BUNDLE_FILE to $SCRIPT_DIR..."
#     mv "$BUNDLE_FILE" "$SCRIPT_DIR"
#     if [ $? -ne 0 ]; then
#         echo "Error moving $BUNDLE_FILE to $SCRIPT_DIR."
#         exit 1
#     fi
# else
#     echo "Error: $BUNDLE_FILE not found."
#     exit 1
# fi

# 9. Create macOS package
echo "Creating macOS package..."
pkgbuild --root ./dist/agent-zero \
         --identifier frdel.agent-zero \
         --install-location /tmp/agent-zero \
         --scripts ./mac_pkg_scripts \
         agent-zero-preinstalled-mac-m1.pkg
if [ $? -ne 0 ]; then
    echo "Error creating macOS package."
    exit 1
fi

# 10. Remove the agent-zero folder
echo "Deleting agent-zero folder..."
cd ..
rm -rf agent-zero
if [ -d "agent-zero" ]; then
    echo "Error: Failed to delete agent-zero folder."
    exit 1
fi

echo "Script completed."
