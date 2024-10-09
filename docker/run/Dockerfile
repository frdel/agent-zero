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
    git \
    && rm -rf /var/lib/apt/lists/*

# Set up SSH
RUN mkdir /var/run/sshd && \ 
    echo 'root:toor' | chpasswd && \ 
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

# Create a new user with UID 1000 (you can change this if needed)
RUN useradd -m user && echo "user:1001" | chpasswd && adduser user sudo 

# Allow 'user' to run sudo without a password
RUN echo "user ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers 

# Create and activate Python virtual environment for the new user
ENV VIRTUAL_ENV=/opt/venv 
RUN python3 -m venv $VIRTUAL_ENV 

# Copy initial .bashrc with virtual environment activation to a temporary location 
COPY .bashrc /etc/skel/.bashrc 

# Copy the script to ensure .bashrc is in the root directory 
COPY initialize.sh /usr/local/bin/initialize.sh 
RUN chmod +x /usr/local/bin/initialize.sh 

# Ensure pip setup in virtual environment before switching users  
RUN $VIRTUAL_ENV/bin/pip install --upgrade pip  

# Expose SSH port  
EXPOSE 22  

CMD ["/usr/local/bin/initialize.sh"]
