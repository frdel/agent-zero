# Use the latest slim version of Debian
# FROM --platform=$TARGETPLATFORM debian:bookworm-slim

# Specify the base image with CUDA support
FROM --platform=$TARGETPLATFORM nvidia/cuda:11.0.3-base-ubuntu20.04

# Set ARG for platform-specific commands
ARG TARGETPLATFORM

# Set environment variables
ENV TZ=America/Chicago
ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/usr/bin:$PATH"

# Update and install necessary packages, including tzdata
RUN apt-get update && apt-get install -y \
    tzdata \
    python3 \
    python3-pip \
    nodejs \
    npm \
    openssh-server \
    sudo \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Set up timezone
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && dpkg-reconfigure -f noninteractive tzdata

# Set up SSH
RUN mkdir /var/run/sshd && \
    echo 'root:toor' | chpasswd && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

# Copy initial .bashrc with virtual environment activation to a temporary location
COPY .bashrc /etc/skel/.bashrc

# Copy the script to ensure .bashrc is in the root directory
COPY initialize.sh /usr/local/bin/initialize.sh
RUN chmod +x /usr/local/bin/initialize.sh

# Ensure pip is upgraded and install Python packages globally
RUN python3 -m pip install --upgrade pip

# Install required Python packages globally with no cache and to the target directory
RUN python3 -m pip install --target=/usr/local/lib/python3.8/dist-packages \
    numpy scipy pandas torch torchvision torchaudio \
    tensorflow scikit-learn transformers accelerate diffusers \
    opencv-python matplotlib seaborn

# Expose SSH port
EXPOSE 22

# Init .bashrc
CMD ["/usr/local/bin/initialize.sh"]
