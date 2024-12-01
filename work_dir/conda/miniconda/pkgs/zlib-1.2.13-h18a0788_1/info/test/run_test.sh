

set -ex



test -f ${PREFIX}/include/zlib.h
test -f ${PREFIX}/lib/libz.a
test -f ${PREFIX}/lib/libz.dylib
exit 0
