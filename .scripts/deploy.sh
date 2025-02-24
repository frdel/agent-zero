#!/bin/bash
set -e

echo "Deployment started ..."

# Pull the latest version of the app
git reset --hard HEAD || { echo "Git reset failed!"; exit 1; }
git pull origin main || { echo "Git pull failed!"; exit 1; }
echo "New changes copied to server!"

# Stop and remove the existing container if it's running
if docker ps -q -f name=agent_zero; then
    docker stop agent_zero || { echo "Failed to stop existing container!"; exit 1; }
    docker rm agent_zero || { echo "Failed to remove existing container!"; exit 1; }
    echo "Old container stopped and removed."
else
    echo "No running container found."
fi

# Run the new container
docker run -d --name agent_zero -p 50080:80 -v $(pwd):/a0 frdel/agent-zero-run || { echo "Docker run failed!"; exit 1; }
#docker run -d --name agent_zero -p 50080:80 -v $(pwd):/a0 frdel/agent-zero-run:testing || { echo "Docker run failed!"; exit 1; }
echo "New container started."

echo "Deployment finished!"