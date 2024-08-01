# Use the latest slim version of Debian
# FROM --platform=$TARGETPLATFORM debian:bookworm-slim

# Use NVIDIA's base CUDA image
FROM nvidia/cuda:11.0.3-base-ubuntu20.04

# Set ARG for platform-specific commands
ARG TARGETPLATFORM

# Update and install necessary packages
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    nodejs \
    npm \
    openssh-server \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Set up SSH
RUN mkdir /var/run/sshd && \
    echo 'root:toor' | chpasswd && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

# Create and activate Python virtual environment
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN python3 -m venv $VIRTUAL_ENV

# Upgrade pip and install packages within the virtual environment #not working currently
# RUN $VIRTUAL_ENV/bin/pip install --upgrade pip && \
    # $VIRTUAL_ENV/bin/pip install numpy && \
    # $VIRTUAL_ENV/bin/pip install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu110

# Copy initial .bashrc with virtual environment activation to a temporary location
COPY .bashrc /etc/skel/.bashrc

# Copy the script to ensure .bashrc is in the root directory
COPY initialize.sh /usr/local/bin/initialize.sh
RUN chmod +x /usr/local/bin/initialize.sh

# Expose SSH port
EXPOSE 22

# Init .bashrc
CMD ["/usr/local/bin/initialize.sh"]

