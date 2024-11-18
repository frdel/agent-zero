# Use the latest slim version of Debian
FROM debian:bookworm-slim

# Update and install necessary packages
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    python3-babel \
    python3-venv \
    nodejs \
    npm \
    openssh-server \
    sudo \
    curl \
    wget \
    git \
    build-essential \
    ffmpeg 

# Cleanup package list
RUN rm -rf /var/lib/apt/lists/*

# Set up SSH
RUN mkdir /var/run/sshd && \
    echo 'root:toor' | chpasswd && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

# Copy contents of the project to /a0
COPY ./fs/ /

# install a0
RUN bash /ins/install_A0.sh

# install additional software
RUN bash /ins/install_searxng.sh

# Expose ports
# EXPOSE 22
EXPOSE 80

# initialize runtime
CMD ["/bin/bash", "/exe/initialize.sh"]