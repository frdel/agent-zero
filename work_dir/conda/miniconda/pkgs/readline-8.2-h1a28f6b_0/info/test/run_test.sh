

set -ex



test -f ${PREFIX}/lib/libreadline.a
test -f ${PREFIX}/lib/libreadline${SHLIB_EXT}
test -f ${PREFIX}/lib/libhistory.a
test -f ${PREFIX}/lib/libhistory${SHLIB_EXT}
python -c "import readline"
exit 0
