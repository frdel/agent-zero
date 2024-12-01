#!/bin/bash

# Isolate the build.
mkdir -p build-cpp
cd build-cpp || exit 1

if [[ "$PKG_NAME" == *static ]]; then
    BUILD_TYPE="-DBUILD_SHARED_LIBS=OFF"
else
    BUILD_TYPE="-DBUILD_SHARED_LIBS=ON"
fi


# Generate the build files.
echo "CMAKE_ARGS: ${CMAKE_ARGS}"
echo "SRC_DIR: ${SRC_DIR}"
cmake -G "Ninja" \
      ${CMAKE_ARGS} \
      ${BUILD_TYPE} \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_INSTALL_PREFIX=$PREFIX \
      -DCMAKE_INSTALL_LIBDIR=lib \
      -DREPROC++=ON \
      -DREPROC_TEST=ON \
      ${SRC_DIR}


# Build, test, and install.
ninja || exit 1
if [[ "$CONDA_BUILD_CROSS_COMPILATION" != "1" ]]; then
    ninja test || exit 1
fi
ninja install || exit 1
