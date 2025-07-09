#!/bin/bash

# Enable exit on error
set -e

# Define variables
REPO_URL="https://github.com/frdel/agent-zero.git"
REPO_DIR="agent-zero"

# Clone the repository if it doesn't exist
if [ ! -d "$REPO_DIR" ]; then
    echo "Cloning the repository..."
    git clone "$REPO_URL"
    echo "Repository cloned successfully."
else
    echo "Repository already exists. Pulling latest changes..."
    cd "$REPO_DIR"
    git pull
    echo "Repository updated successfully."
    cd ..
fi

# Change to the repository directory
cd "$REPO_DIR"

# Set up environment variables
echo "Setting up environment variables..."
if [ ! -f ".env" ]; then
    echo ".env file not found, copying from example.env..."
    cp example.env .env
fi
echo "Environment variables set up."

# Install Python dependencies
echo "Checking for Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "Python is not installed. Please install Python and try again."
    exit 1
fi

echo "Installing Python dependencies..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
echo "Python dependencies installed."

# Install Docker (optional)
echo "Checking for Docker installation..."
if ! command -v docker &> /dev/null; then
    echo "Docker is not installed. You can download and install Docker from https://www.docker.com/products/docker-desktop"
    echo "Skipping Docker setup."
else
    echo "Docker is installed. Setting up Docker container..."
    docker pull frdel/agent-zero-exe
    echo "Docker container setup complete."
fi

# Run the main program
echo "Running the Agent Zero framework..."
python3 main.py

# Keep the terminal open after execution
echo "Agent Zero setup and execution complete."
exec "$SHELL"
