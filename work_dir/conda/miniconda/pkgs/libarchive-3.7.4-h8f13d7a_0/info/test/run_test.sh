

set -ex



test -f "${PREFIX}/lib/pkgconfig/libarchive.pc"
test -f "${PREFIX}/include/archive.h"
test -f "${PREFIX}/include/archive_entry.h"
test -f "${PREFIX}/lib/libarchive.a"
test -f "${PREFIX}/lib/libarchive${SHLIB_EXT}"
bsdcat --version
bsdcpio --version
bsdtar --version
pushd test-archives
bsdtar -vxf hello_world.xar 2>&1 | rg "x hello_world"
bsdtar -vxf archive.7z 2>&1 | rg "x 7zip-archive"
bsdtar -vxf hello_world.tar.zst 2>&1 | rg "greets"
popd
exit 0
