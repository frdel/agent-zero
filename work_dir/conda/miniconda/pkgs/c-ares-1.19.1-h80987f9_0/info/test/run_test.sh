

set -ex



test -f ${PREFIX}/include/ares.h
test -f ${PREFIX}/lib/libcares${SHLIB_EXT}
test ! -f ${PREFIX}/lib/libcares.a
test ! -f ${PREFIX}/lib/libcares_static.a
exit 0
