#!/bin/bash
set -e

echo "====================BASE PACKAGES START===================="

apt-get update && apt-get upgrade -y

apt-get install -y --no-install-recommends \
    nodejs npm openssh-server sudo curl wget git ffmpeg supervisor cron

echo "====================BASE PACKAGES NPM===================="

# we shall not install npx separately, it's discontinued and some versions are broken
# npm i -g npx
npm i -g shx

echo "====================BASE PACKAGES END===================="
