#!/usr/bin/env bash

# Not only does this hopefully make pcre2 faster,
# it fixes a test failure on macOS. See link below.
#
# ref: https://bugs.exim.org/show_bug.cgi?id=1642
#
CFLAGS="${CFLAGS} -O3"
CXXFLAGS="${CXXFLAGS} -O3"

if [[ "$target_platform" == "osx-64" ]]; then
    CXXFLAGS="$CXXFLAGS -DTARGET_OS_OSX=1"
    CFLAGS="$CFLAGS -DTARGET_OS_OSX=1"
fi

if [[ "$target_platform" == "osx-arm64" ]]; then
    CMAKE_ARGS="${CMAKE_ARGS} -DPCRE2_SUPPORT_JIT=OFF"
else
    CMAKE_ARGS="${CMAKE_ARGS} -DPCRE2_SUPPORT_JIT=ON"
fi

mkdir build_cmake
pushd build_cmake
cmake ${CMAKE_ARGS} \
    -DBUILD_SHARED_LIBS=ON \
    -DCMAKE_BUILD_TYPE=release \
    -DCMAKE_INSTALL_LIBDIR=lib \
    -DCMAKE_INSTALL_PREFIX=$PREFIX \
    -DPCRE2_BUILD_PCRE2_16=ON \
    -DPCRE2_BUILD_PCRE2_32=ON \
    -DPCRE2_SUPPORT_LIBREADLINE=OFF \
    -GNinja \
    ..

ninja
ninja test
ninja install
