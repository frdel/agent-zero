#!/bin/sh

# Enter test directory.
cd test  || exit 1

# Isolate the build.
mkdir Build
cd Build || exit 1

# Generate the build files, compile the test, and run it.
cmake .. -GNinja -DCMAKE_PREFIX_PATH=$PREFIX
ninja || exit 1
./test || exit 1


# Perform additional testing.
test -f $PREFIX/lib/libyaml-cpp.so  || test -f $PREFIX/lib/libyaml-cpp.dylib || exit 1
