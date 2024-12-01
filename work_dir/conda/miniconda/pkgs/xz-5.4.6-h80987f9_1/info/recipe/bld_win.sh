#!/bin/bash

cd $SRC_DIR

export BUILD=x86_64-w64-mingw32
export HOST=x86_64-w64-mingw32
# See $SRC_DIR/windows/build.bash for more info.
./configure \
      --prefix=${PREFIX} \
      --enable-silent-rules \
      --disable-dependency-tracking \
      --disable-nls \
      --disable-scripts \
      --disable-threads \
      --disable-shared \
      --enable-small \
      --build=$BUILD \
      CFLAGS="-march=x86-64 -mtune=generic -Os"

make -j${CPU_COUNT} ${VERBOSE_AT}
make check
make install

# Move command-line tools to their windows location.
mv ${PREFIX}/bin/* $LIBRARY_BIN

mv src/liblzma/api/lzma $LIBRARY_INC
cp src/liblzma/api/lzma.h $LIBRARY_INC

[[ -d ${LIBRARY_LIB}/pkgconfig ]] || mkdir ${LIBRARY_LIB}/pkgconfig
cp src/liblzma/liblzma.pc ${LIBRARY_LIB}/pkgconfig

# Remove posix style directories
rm -rf ${PREFIX}/lib
rm -rf ${PREFIX}/include
rm -rf ${PREFIX}/share
rm -rf ${PREFIX}/bin

find $PREFIX -name '*.la' -delete
