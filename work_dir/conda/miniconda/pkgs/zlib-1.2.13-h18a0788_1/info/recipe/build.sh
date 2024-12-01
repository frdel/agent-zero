#!/bin/bash

# Set flags
export CFLAGS=$(echo ${CFLAGS} | sed 's|-O2|-O3|g')
export CPPFLAGS=$(echo ${CPPFLAGS} | sed 's|-O2|-O3|g')

MACH=$(${CC} -dumpmachine)
if [[ ${MACH} =~ x86_64.* ]] || [[ ${MACH} =~ i?86.* ]]; then
  export CFLAGS="${CFLAGS} -DUNALIGNED_OK"
fi
export CFLAGS="${CFLAGS} -fPIC"
export CXXFLAGS="${CXXFLAGS} -fPIC"

# linux-aarch64 activations fails to set `ar` tool. This can be
# removed when activations is corrected.
if [[ "${target_platform}" == linux-aarch64 ]]; then
  if [[ -n "$AR" ]]; then
      CMAKE_ARGS="${CMAKE_ARGS} -DCMAKE_AR=${AR}"
  fi
fi

# Isolate the build.
mkdir -p Build
cd Build || exit 1


# Generate the build files.
echo "Generating the build files."
cmake .. ${CMAKE_ARGS} \
      -G"Unix Makefiles" \
      -DCMAKE_PREFIX_PATH=$PREFIX \
      -DCMAKE_INSTALL_PREFIX=$PREFIX \
      -DCMAKE_BUILD_TYPE=Release \

# Build.
echo "Building..."
make  -j${CPU_COUNT} || exit 1


# Perform tests.
echo "Testing..."
ctest -VV --output-on-failure || exit 1


# Installing
echo "Installing..."
make install || exit 1

# Remove man files.
rm -rf $PREFIX/share

# Copy license file to the source directory so conda-build can find it.
cp $RECIPE_DIR/license.txt $SRC_DIR/license.txt


# Error free exit!
echo "Error free exit!"
exit 0
