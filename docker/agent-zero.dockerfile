FROM python:3.12-slim

ARG UID=1000 \
    GID=1000 \
    USER=user \
    GROUP=group
ENV UID=$UID \
    GID=$GID \
    USER=$USER \
    GROUP=$GROUP \
    PATH=/home/$USER/.local/bin:$PATH

# fix user/group from host
RUN set -eux \
    && if getent passwd $USER ; then userdel -f $USER; fi \
    && if getent passwd $UID ; then userdel -f $(id -un $UID); fi \
    && if getent group $GROUP ; then groupdel $(id -gn $GROUP); fi \
    && if getent group $GID ; then groupmod --gid 200 $(getent group $GID | cut -d: -f1); fi \
    && groupadd -g $GID $GROUP \
    && useradd -l -u $UID -g $GROUP $USER \
    && install -d -m 0755 -o $USER -g $GROUP /home/$USER

RUN apt-get update && apt-get install -y \
    curl \
    sudo \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
USER $USER:$GROUP
