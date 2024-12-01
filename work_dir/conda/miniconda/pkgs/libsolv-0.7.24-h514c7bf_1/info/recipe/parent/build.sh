#!/bin/bash
echo "Building ${PKG_NAME}."

# Isolate the build.
mkdir -p build
cd build || exit 1


# Generate the build files.
echo "Generating the build files..."
cmake .. ${CMAKE_ARGS} \
-GNinja \
-DCMAKE_PREFIX_PATH=$PREFIX \
-DCMAKE_INSTALL_PREFIX=$PREFIX \
-DCMAKE_BUILD_TYPE=Release \
-DCMAKE_INSTALL_LIBDIR=lib \
-DENABLE_CONDA=ON \
-DMULTI_SEMANTICS=ON \
-DENABLE_PCRE2=ON \
-DENABLE_STATIC=ON


# Build.
echo "Building..."
ninja || exit 1


# Perform tests.
#  echo "Testing..."
#  ninja test || exit 1
#  path_to/test || exit 1
#  ctest -VV --output-on-failure || exit 1


# Installing
#echo "Installing..."
#ninja install || exit 1


# Error free exit!
echo "Error free exit!"
exit 0
