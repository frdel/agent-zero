# Use the latest slim version of Debian
FROM --platform=$TARGETPLATFORM debian:bookworm-slim

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
    curl \
    wget \
    git \
    ffmpeg

# Cleanup package list
RUN rm -rf /var/lib/apt/lists/*

# Set up SSH
RUN mkdir /var/run/sshd && \
    echo 'root:toor' | chpasswd && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

# Create and activate Python virtual environment
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV

# Copy contents of filesystem directory to /
COPY ./fs/ /

# Ensure the virtual environment and pip setup
RUN $VIRTUAL_ENV/bin/pip install --upgrade pip

# Install additional python packages
RUN $VIRTUAL_ENV/bin/pip install \
    ipython \
    requests

# Clone Agent Zero repository
RUN git clone --branch development https://github.com/frdel/agent-zero.git /git/agent-zero

# Install A0 python packages
RUN $VIRTUAL_ENV/bin/pip install -r /git/agent-zero/requirements.txt
# Preload A0
RUN $VIRTUAL_ENV/bin/python /git/agent-zero/preload.py



# Clone additional git repos
RUN git clone https://github.com/searxng/searxng.git /git/searxng


# install additional software
RUN bash /ins/install_searxng.sh



# Expose ports
EXPOSE 22 80

# initialize runtime
CMD ["/bin/bash", "/exe/initialize.sh"]