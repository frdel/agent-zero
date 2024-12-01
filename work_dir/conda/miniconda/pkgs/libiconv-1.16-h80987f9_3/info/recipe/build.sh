#!/bin/bash

set -x

cp -r ${BUILD_PREFIX}/share/libtool/build-aux/config.* ./build-aux/
cp -r ${BUILD_PREFIX}/share/libtool/build-aux/config.* ./libcharset/build-aux/

mkdir -p $PREFIX/lib

./configure --prefix=${PREFIX}  \
            --host=${HOST}      \
            --build=${HOST}    \
            --enable-static     \
            --disable-rpath

make -j${CPU_COUNT} ${VERBOSE_AT}

make check
make install

# TODO :: Only provide a static iconv executable for GNU/Linux.
# TODO :: glibc has iconv built-in. I am only providing it here
# TODO :: for legacy packages (and through gritted teeth).
if [[ ${HOST} =~ .*linux.* ]]; then
  chmod 755 ${PREFIX}/lib/libiconv.so.*
  chmod 755 ${PREFIX}/lib/libcharset.so.*
  if [ -f ${PREFIX}/lib/preloadable_libiconv.so ]; then
    chmod 755 ${PREFIX}/lib/preloadable_libiconv.so
  fi
fi

# remove libtool files
find $PREFIX -name '*.la' -delete
