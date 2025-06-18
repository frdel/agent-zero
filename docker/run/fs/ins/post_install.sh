#!/bin/bash
set -e

# Cleanup package list
rm -rf /var/lib/apt/lists/*
apt-get clean