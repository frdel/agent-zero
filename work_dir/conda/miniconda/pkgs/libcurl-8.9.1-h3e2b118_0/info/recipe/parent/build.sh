#!/bin/bash
set -ex

# Get an updated config.sub and config.guess
cp $BUILD_PREFIX/share/libtool/build-aux/config.* .

test -n "${AUTORECONF}" \
&& autoreconf \
    --warnings=all \
    --install \
    --force

# need macosx-version-min flags set in cflags and not cppflags
export CFLAGS="$CFLAGS $CPPFLAGS"

./configure \
    --prefix=${PREFIX} \
    --host=${HOST} \
    --disable-ldap \
    --disable-manual \
    --with-ca-bundle=${PREFIX}/ssl/cacert.pem \
    --with-ssl=${PREFIX} \
    --with-zlib=${PREFIX} \
    --with-gssapi=${PREFIX} \
    --with-libssh2=${PREFIX} \
    --with-nghttp2=${PREFIX} \
|| cat config.log

make -j${CPU_COUNT} ${VERBOSE_AT}

# -v: verbose
# -a: keep going on failure (so we see everything which breaks, not just the first failing test)
# -k: keep test files after completion
# -am: automake style TAP output
# -p: print logs if test fails
# -j: parallelization
# disable test 433, since it requires the glibc debug info
# disable test 1173 and 1139 since --disable-manual is set
# disable test 971, 1705, and 1706 because of locale settings on osx
make TFLAGS="-v -a -k -p -j$(CPU_COUNT) !433 !1173 !1139 !971 !1705 !1706" test-nonflaky

make install

# Includes man pages and other miscellaneous.
rm -rf "${PREFIX}/share"

