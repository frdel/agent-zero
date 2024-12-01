#!/bin/bash

# Get an updated config.sub and config.guess
# Running autoreconf messes up the build so just copy these two files
cp $BUILD_PREFIX/share/libtool/build-aux/config.* .

set -x

if [[ $target_platform =~ osx-.* ]]; then
    export cf_cv_mixedcase=no
fi

if [ ! -f "${BUILD_PREFIX}/bin/strip" ]; then
    ln -sf "${HOST}-strip" "${BUILD_PREFIX}/bin/strip"
fi

export PKG_CONFIG_LIBDIR=$PREFIX/lib/pkgconfig

./configure \
  --prefix=$PREFIX \
  --host=${HOST} \
  --without-debug \
  --without-ada \
  --without-manpages \
  --with-shared \
  --with-pkg-config \
  --with-pkg-config-libdir=$PREFIX/lib/pkgconfig \
  --disable-overwrite \
  --enable-symlinks \
  --enable-termcap \
  --enable-pc-files \
  --with-termlib \
  --enable-widec

if [[ "$target_platform" == osx* ]]; then
  # When linking libncurses*.dylib, reexport libtinfo[w] so that later
  # client code linking against just -lncurses[w] also gets -ltinfo[w].
  sed -i.orig '/^SHLIB_LIST/s/-ltinfo/-Wl,-reexport&/' ncurses/Makefile
fi

make -j${CPU_COUNT} ${VERBOSE_AT}
make install

if [[ ${HOST} =~ .*linux.* ]]; then
  _SOEXT=.so
else
  _SOEXT=.dylib
fi

# Make symlinks from the wide to the non-wide libraries.
echo "Making symlinks from the wide to the non-wide libraries."
pushd "${PREFIX}"/lib
  for _LIB in ncurses ncurses++ form panel menu tinfo; do
    for WIDE_LIBFILE in $(ls lib${_LIB}w*${_SOEXT}*); do
      NONWIDE_LIBFILE=${WIDE_LIBFILE/${_LIB}w/${_LIB}}
      ln -s ${WIDE_LIBFILE} ${NONWIDE_LIBFILE}
    done
    if [[ -f lib${_LIB}w.a ]]; then
      ln -s lib${_LIB}w.a lib${_LIB}.a
    fi
  done
popd

# Provide headers in `$PREFIX/include` and
# symlink them in `$PREFIX/include/ncurses`
# and in `$PREFIX/include/ncursesw`.
HEADERS_DIR_W="${PREFIX}/include/ncursesw"
HEADERS_DIR="${PREFIX}/include/ncurses"
mkdir -p "${HEADERS_DIR}"
for HEADER in $(ls $HEADERS_DIR_W); do
  mv "${HEADERS_DIR_W}/${HEADER}" "${PREFIX}/include/${HEADER}"
  ln -s "${PREFIX}/include/${HEADER}" "${HEADERS_DIR_W}/${HEADER}"
  ln -s "${PREFIX}/include/${HEADER}" "${HEADERS_DIR}/${HEADER}"
done
