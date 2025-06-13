#!/bin/bash

# Install yt-dlp and ffmpeg
sudo apt-get update && sudo apt-get install -y yt-dlp ffmpeg

# Install yt-dlp using pip
pip install --upgrade yt-dlp

# Call the Python script to download the video
python3 /a0/instruments/default/yt_download/download_video.py "$1"
