#!/bin/bash

# Define script location and default directories
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
PYTHON_SCRIPT="${SCRIPT_DIR}/music_generation.py"
DEFAULT_OUTPUT_DIR="/root/generated_music"

# Display help information if no arguments provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <prompt>"
    echo ""
    echo "Example: $0 \"An upbeat electronic track with a catchy melody\""
    exit 1
fi

# Check if the Python script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "Error: Python script not found at $PYTHON_SCRIPT"
    echo "Make sure music_generation.py is in the same directory as this shell script."
    exit 1
fi

# Make sure the Python script is executable
chmod +x "$PYTHON_SCRIPT"

# Ensure output directory exists
mkdir -p "$DEFAULT_OUTPUT_DIR"

# Execute the Python script with the prompt
echo "🎵 Starting AI Music Generation..."
echo "📂 Output will be saved to $DEFAULT_OUTPUT_DIR"

python3 "$PYTHON_SCRIPT" "$@"

# Check if generation was successful
if [ $? -eq 0 ]; then
    echo "✅ Music generation completed successfully!"
    
    # List the generated files
    LATEST_FILE=$(ls -t "$DEFAULT_OUTPUT_DIR"/*.mp3 2>/dev/null | head -n 1)
    
    if [ -n "$LATEST_FILE" ]; then
        echo "📁 Latest generated file: $LATEST_FILE"
        echo "🔊 You can play this file with a media player"
    fi
else
    echo "❌ Music generation failed"
    exit 1
fi