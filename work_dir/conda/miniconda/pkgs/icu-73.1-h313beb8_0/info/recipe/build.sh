#!/bin/bash
# Get an updated config.sub and config.guess
cp $BUILD_PREFIX/share/libtool/build-aux/config.* ./source

set -e

cd source

chmod +x configure install-sh

EXTRA_OPTS=""

if [[ "$CONDA_BUILD_CROSS_COMPILATION" == "1" ]]; then
    mkdir cross_build
    pushd cross_build
    CC=$CC_FOR_BUILD CXX=$CXX_FOR_BUILD AR= AS= LD= CFLAGS= CXXFLAGS= LDFLAGS= CPPFLAGS= ../configure \
      --build=${BUILD} \
      --host=${BUILD} \
      --disable-samples \
      --disable-extras \
      --disable-layout \
      --disable-tests
    make -j${CPU_COUNT}
    EXTRA_OPTS="$EXTRA_OPTS --with-cross-build=$PWD"
    popd
fi

if [[ ${HOST} =~ .*darwin.* ]]; then
  EXTRA_OPTS="$EXTRA_OPTS --enable-rpath"
fi

./configure --prefix="${PREFIX}"  \
            --build=${BUILD}      \
            --host=${HOST}        \
            --disable-samples     \
            --disable-extras      \
            --disable-layout      \
            --disable-tests       \
            --enable-static       \
            ${EXTRA_OPTS}

make -j${CPU_COUNT} ${VERBOSE_CM}
if [[ "${CONDA_BUILD_CROSS_COMPILATION}" != "1" ]]; then
  make check
fi
make install

rm -rf ${PREFIX}/sbin
