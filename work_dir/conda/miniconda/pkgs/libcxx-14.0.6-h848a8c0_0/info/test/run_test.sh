

set -ex



echo 1
test -f $PREFIX/include/c++/v1/iterator
bash compile_test.sh
if [ -f $PREFIX/lib/libc++abi.dylib ]; then exit 1; fi
exit 0
