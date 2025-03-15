#!/bin/bash

# Sanitize thinking tags from terminal output
# This script removes <think>, </think>, <thinking>, and </thinking> tags 
# from both stdout and stderr in real-time while preserving the rest of the line.
#
# Usage: ./sanitize_tags.sh command [args...]
#
# Example: ./sanitize_tags.sh python app.py

# Combine stdout and stderr, process once, then redirect back
exec "$@" 2>&1 | sed -E 's/<\/?think(ing)?>//g' 