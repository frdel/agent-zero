

set -ex



curl-config --features
curl-config --protocols
test -f ${PREFIX}/lib/libcurl${SHLIB_EXT}
test ! -f ${PREFIX}/lib/libcurl.a
exit 0
