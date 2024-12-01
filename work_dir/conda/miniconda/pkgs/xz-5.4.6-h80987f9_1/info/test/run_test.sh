

set -ex



xz --help
unxz --help
lzma --help
test -f ${PREFIX}/include/lzma.h
test -f ${PREFIX}/lib/pkgconfig/liblzma.pc
test -f `pkg-config --variable=libdir --dont-define-prefix liblzma`/liblzma${SHLIB_EXT}
test -f ${PREFIX}/lib/liblzma.a
test -f ${PREFIX}/lib/liblzma${SHLIB_EXT}
test -f ${PREFIX}/lib/liblzma.5${SHLIB_EXT}
conda inspect linkages -p $PREFIX $PKG_NAME
conda inspect objects -p $PREFIX $PKG_NAME
exit 0
