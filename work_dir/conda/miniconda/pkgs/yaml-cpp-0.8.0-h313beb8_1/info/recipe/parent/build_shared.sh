#!/bin/bash

# Isolate the build.
mkdir build_shared
cd build_shared || exit 1

# Generate the build files.
cmake .. -G"Ninja" ${CMAKE_ARGS} \
    -DBUILD_SHARED_LIBS=ON \
    -DYAML_BUILD_SHARED_LIBS=ON \
    -DYAML_CPP_BUILD_TESTS=ON \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_PREFIX_PATH=$PREFIX \
    -DCMAKE_INSTALL_PREFIX=$PREFIX \
    -DYAML_CPP_INSTALL=ON

# Build and install.
ninja install || exit 1

# Call author's tests.
test/yaml-cpp-tests || exit 1
