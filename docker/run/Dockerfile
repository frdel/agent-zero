# Use the latest slim version of Debian
FROM debian:bookworm-slim

# Check if the argument is provided, else throw an error
ARG BRANCH
RUN if [ -z "$BRANCH" ]; then echo "ERROR: BRANCH is not set!" >&2; exit 1; fi

# Update and install necessary packages
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    nodejs \
    npm \
    openssh-server \
    sudo \
    curl \
    wget \
    git \
    ffmpeg 

# Set up SSH
RUN mkdir /var/run/sshd && \
    echo 'root:toor' | chpasswd && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

# Copy contents of the project to /a0
COPY ./fs/ /

# install additional software
RUN bash /ins/install_searxng.sh

# install A0
RUN bash /ins/install_A0.sh $BRANCH

# cleanup repo and install A0 without caching, this speeds up builds
ARG CACHE_DATE=none
RUN echo "cache buster $CACHE_DATE" && bash /ins/install_A02.sh $BRANCH

# Cleanup package list
RUN rm -rf /var/lib/apt/lists/*
RUN apt-get clean

# Expose ports
# EXPOSE 22
EXPOSE 80

# initialize runtime
CMD ["/bin/bash", "/exe/initialize.sh"]