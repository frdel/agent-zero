#!/bin/bash

set -e
set -o pipefail

# Cleanup package list
rm -rf /var/lib/apt/lists/*
apt-get clean
