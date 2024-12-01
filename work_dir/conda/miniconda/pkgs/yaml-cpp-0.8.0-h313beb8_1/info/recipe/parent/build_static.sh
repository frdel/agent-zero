#!/bin/bash

# Isolate the build.
mkdir build_static
cd build_static || exit 1

# Generate the build files.
cmake .. -G"Ninja" ${CMAKE_ARGS} \
      -DYAML_BUILD_SHARED_LIBS=OFF \
      -DYAML_CPP_BUILD_TESTS=OFF \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_PREFIX_PATH=$PREFIX \
      -DCMAKE_INSTALL_PREFIX=$PREFIX \
      -DYAML_CPP_INSTALL=ON

# Build and install.
ninja install || exit 1
