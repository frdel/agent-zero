

set -ex



test -d ${PREFIX}/include/fmt
test -f ${PREFIX}/include/fmt/core.h
test -f ${PREFIX}/include/fmt/format.h
test -f ${PREFIX}/lib/cmake/fmt/fmt-config.cmake
test -f ${PREFIX}/lib/libfmt.dylib
exit 0
