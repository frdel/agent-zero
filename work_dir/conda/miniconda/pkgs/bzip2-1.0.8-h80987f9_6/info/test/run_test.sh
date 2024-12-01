

set -ex



bzip2 --help
test -f ${PREFIX}/bin/bunzip2
test -f ${PREFIX}/bin/bzcat
test -f ${PREFIX}/bin/bzcmp
test -f ${PREFIX}/bin/bzdiff
test -f ${PREFIX}/bin/bzegrep
test -f ${PREFIX}/bin/bzfgrep
test -f ${PREFIX}/bin/bzgrep
test -f ${PREFIX}/bin/bzip2recover
test -f ${PREFIX}/bin/bzip2
test -f ${PREFIX}/bin/bzless
test -f ${PREFIX}/bin/bzmore
test -f ${PREFIX}/include/bzlib.h
test -f ${PREFIX}/lib/libbz2.a
test -f ${PREFIX}/lib/libbz2${SHLIB_EXT}
exit 0
