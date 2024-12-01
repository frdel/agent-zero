

set -ex



test -f ${PREFIX}/include/reproc++/reproc.hpp
test -f ${PREFIX}/lib/libreproc++${SHLIB_EXT}
test -f ${PREFIX}/lib/cmake/reproc++/reproc++-config.cmake
test ! -f ${PREFIX}/lib/libreproc++.a
exit 0
