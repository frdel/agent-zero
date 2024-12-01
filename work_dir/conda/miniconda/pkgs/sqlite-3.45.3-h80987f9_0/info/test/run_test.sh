

set -ex



sqlite3 --version
test -f $PREFIX/bin/sqlite3
test -f $PREFIX/lib/libsqlite3${SHLIB_EXT}
test ! -f $PREFIX/lib/libsqlite3.a
test -f $PREFIX/include/sqlite3.h
test -f $PREFIX/include/sqlite3ext.h
test -f $PREFIX/lib/pkgconfig/sqlite3.pc
exit 0
