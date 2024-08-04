# Specify the base image with CUDA support
FROM --platform=$TARGETPLATFORM nvidia/cuda:11.0.3-base-ubuntu20.04
# FROM --platform=$TARGETPLATFORM debian:bookworm-slim

# Set ARG for platform-specific commands
ARG TARGETPLATFORM

# Set environment variables
ENV TZ=America/Chicago
ENV DEBIAN_FRONTEND=noninteractive

# Update and install necessary packages, including tzdata
RUN apt-get update && apt-get install -y \
    tzdata \
    python3 \
    python3-pip \
    python3-venv \
    nodejs \
    npm \
    openssh-server \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Set up timezone
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && dpkg-reconfigure -f noninteractive tzdata

# Set up SSH
RUN mkdir /var/run/sshd && \
    echo 'root:toor' | chpasswd && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

# Create and activate Python virtual environment
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV

# Copy initial .bashrc with virtual environment activation to a temporary location
COPY .bashrc /etc/skel/.bashrc

# Copy the script to ensure .bashrc is in the root directory
COPY initialize.sh /usr/local/bin/initialize.sh
RUN chmod +x /usr/local/bin/initialize.sh

# Ensure the virtual environment and pip setup
RUN $VIRTUAL_ENV/bin/pip install --upgrade pip

# Expose SSH port
EXPOSE 22

# Init .bashrc
CMD ["/usr/local/bin/initialize.sh"]