

set -ex



nghttp -nv https://nghttp2.org
test ! -f ${PREFIX}/lib/libnghttp2.a
exit 0
