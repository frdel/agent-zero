#!/bin/bash

# Sanitize thinking tags from terminal output
# This script removes <think>, </think>, <thinking>, and </thinking> tags 
# from both stdout and stderr in real-time while preserving the rest of the line.
#
# Usage: ./sanitize_tags.sh command [args...]
#
# Example: ./sanitize_tags.sh python app.py

# Execute the passed command and pipe both stdout and stderr through sed
# to remove thinking tags while keeping the rest of the content
exec "$@" 2> >(sed -E 's/<think(ing)?>//g;s/<\/think(ing)?>//g' >&2) > >(sed -E 's/<think(ing)?>//g;s/<\/think(ing)?>//g') 