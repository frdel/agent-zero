

set -ex



zstd -be -i5
test -f ${PREFIX}/include/zstd.h
test -f ${PREFIX}/lib/libzstd.a
test -f ${PREFIX}/lib/libzstd.dylib
export PKG_CONFIG_PATH=$PREFIX/lib/pkgconfig
test -f ${PREFIX}/lib/pkgconfig/libzstd.pc
pkg-config --cflags libzstd
exit 0
