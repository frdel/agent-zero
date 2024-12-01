#!/bin/bash

# Get an updated config.sub and config.guess
cp -r ${BUILD_PREFIX}/share/libtool/build-aux/config.* ./build-aux

./configure --prefix=${PREFIX}  \
            --build=${BUILD}    \
            --host=${HOST}
make -j${CPU_COUNT} ${VERBOSE_AT}
make check
make install

# remove libtool files
find $PREFIX -name '*.la' -delete
