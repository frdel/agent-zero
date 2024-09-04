# Use the latest slim version of Debian
FROM --platform=$TARGETPLATFORM debian:bookworm-slim

# Set ARG for platform-specific commands
ARG TARGETPLATFORM

ENV DEBIAN_FRONTEND noninteractive
ENV TERM linux

# Define locales.
ENV LANGUAGE en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LC_ALL en_US.UTF-8
ENV LC_CTYPE en_US.UTF-8
ENV LC_MESSAGES en_US.UTF-8

USER root

ARG user_name
# Adding user
RUN useradd -rm -d /home/$user_name -s /bin/bash -g root -G sudo -u 1001 $user_name \
 && echo "${user_name}:${user_name}" | chpasswd


# Update and install necessary packages
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    nodejs \
    npm \
    openssh-server \
    sudo \
    locales \
    && rm -rf /var/lib/apt/lists/*

# Generate the locale
RUN echo "en_US.UTF-8 UTF-8" > /etc/locale.gen && \
    locale-gen en_US.UTF-8 && \
    update-locale LANG=en_US.UTF-8

# Set up SSH
RUN mkdir /var/run/sshd && \
    echo 'root:toor' | chpasswd && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

# Create and activate Python virtual environment
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV

# Copy initial .bashrc with virtual environment activation to a temporary location
COPY .bashrc /etc/skel/.bashrc

WORKDIR /home/$user_name

# Python Dependencies
COPY ./requirements.txt requirements.txt 

# Update the PATH environment variable so that the correct pip and python are used
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN pip install --upgrade pip \
 && pip install --upgrade setuptools \
 && pip install -r requirements.txt

# Copy the script to ensure .bashrc is in the root directory
COPY initialize.sh /home/$user_name/initialize.sh
RUN chmod +x /home/$user_name/initialize.sh
RUN sed -i -e 's/\r$//' /home/$user_name/initialize.sh

# Ensure the virtual environment and pip setup
RUN $VIRTUAL_ENV/bin/pip install --upgrade pip

# Expose SSH port
EXPOSE 22

# Init .bashrc
CMD ["/usr/local/bin/initialize.sh"]


WORKDIR /home/$user_name/work_dir
