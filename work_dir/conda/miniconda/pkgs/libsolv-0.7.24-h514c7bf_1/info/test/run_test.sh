

set -ex



test -f ${PREFIX}/lib/libsolv${SHLIB_EXT}
test -f ${PREFIX}/lib/libsolvext${SHLIB_EXT}
test -f ${PREFIX}/include/solv/repo.h
dumpsolv -h
exit 0
