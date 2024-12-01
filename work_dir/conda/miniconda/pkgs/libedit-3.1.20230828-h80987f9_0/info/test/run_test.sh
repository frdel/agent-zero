

set -ex



test -f $PREFIX/lib/pkgconfig/libedit.pc
test -f $PREFIX/lib/libedit.dylib
exit 0
