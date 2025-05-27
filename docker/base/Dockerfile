# Use the latest slim version of Kali Linux
FROM kalilinux/kali-rolling


# Set locale to en_US.UTF-8 and timezone to UTC
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y locales tzdata
RUN sed -i -e 's/# \(en_US\.UTF-8 .*\)/\1/' /etc/locale.gen && \
    dpkg-reconfigure --frontend=noninteractive locales && \
    update-locale LANG=en_US.UTF-8 LANGUAGE=en_US:en LC_ALL=en_US.UTF-8
RUN ln -sf /usr/share/zoneinfo/UTC /etc/localtime
RUN echo "UTC" > /etc/timezone
RUN dpkg-reconfigure -f noninteractive tzdata
ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8
ENV TZ=UTC

# Copy contents of the project to /
COPY ./fs/ /

# install python
RUN bash /ins/install_python.sh

# install packages software
RUN bash /ins/install_base_packages.sh

# configure ssh
RUN bash /ins/configure_ssh.sh

# Keep container running infinitely
CMD ["tail", "-f", "/dev/null"]
