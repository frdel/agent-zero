#!/bin/bash

# Install yt-dlp and ffmpeg
sudo apt-get update && sudo apt-get install -y yt-dlp ffmpeg

# Download the best video and audio, and merge them
yt-dlp -f bestvideo+bestaudio --merge-output-format mp4 "$1"