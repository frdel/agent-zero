#!/bin/bash

# Default branch is main
BRANCH=${1:-main}

# Build the Docker image with the given branch, with CUDA support
docker build -t frdel/agent-zero-run-cuda:testing --build-arg BRANCH=$BRANCH -f Dockerfile.cuda .

echo "Build complete for CUDA-enabled image: frdel/agent-zero-run-cuda:testing with branch $BRANCH" 