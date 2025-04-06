#!/bin/bash

echo "Starting Agent Zero with CUDA GPU support..."
docker-compose -f docker-compose.cuda.yml up -d

echo "Agent Zero with CUDA is now running."
echo "Access the application at http://localhost:50080"
echo
echo "To stop, run: docker-compose -f docker-compose.cuda.yml down" 