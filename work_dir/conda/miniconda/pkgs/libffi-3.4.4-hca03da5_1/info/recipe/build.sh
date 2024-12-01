#!/bin/bash

set -ex

cd $SRC_DIR

# work-a-round for cyclic dependencies on OSX
if [[ $target_platform == osx-* ]]; then
  conda create -p $SRC_DIR/compilers clang_${target_platform} clangxx_${target_platform} --yes --quiet
  cp -fr compilers/* $BUILD_PREFIX/. 2>/dev/null || true
  # do manual activation ...
  . $BUILD_PREFIX/etc/conda/activate.d/activate_clang_${target_platform}.sh
  . $BUILD_PREFIX/etc/conda/activate.d/activate_clangxx_${target_platform}.sh
fi

export CFLAGS="${CFLAGS//-fvisibility=+([! ])/}"
export CXXFLAGS="${CXXFLAGS//-fvisibility=+([! ])/}"

configure_args=(
    --disable-debug
    --disable-dependency-tracking
    --prefix="${PREFIX}"
    --includedir="${PREFIX}/include"
)

configure_args+=(--build=$BUILD --host=$HOST)

if [[ "$target_platform" == osx-* ]]; then
  export CFLAGS="${CFLAGS} -Wno-deprecated-declarations"
  export CXXFLAGS="${CXXFLAGS} -Wno-deprecated-declarations"
  export CPP="${CC} -E"
  export CXXCPP="${CXX} -E"
else
 autoreconf -vfi
fi

if [[ "$target_platform" == linux* ]]; then
  # this changes the install dir from ${PREFIX}/lib64 to ${PREFIX}/lib
  sed -i 's:@toolexeclibdir@:$(libdir):g' Makefile.in */Makefile.in
  sed -i 's:@toolexeclibdir@:${libdir}:g' libffi.pc.in
fi

./configure "${configure_args[@]}" || { cat config.log; exit 1;}

make -j${CPU_COUNT} ${VERBOSE_AT}
make check
make install

if [[ $target_platform == osx-* ]]; then
  # do manual deactivation ...
  . $BUILD_PREFIX/etc/conda/deactivate.d/deactivate_clang_${target_platform}.sh
  . $BUILD_PREFIX/etc/conda/deactivate.d/deactivate_clangxx_${target_platform}.sh
fi

# This overlaps with libgcc-ng:
rm -rf ${PREFIX}/share/info/dir

# Make sure we provide old variant.  As in 3.4 no API change was introduced in coparison to 3.3
# we will go with the assumption of being backward compatible.
pushd $PREFIX/lib
# make sure we address also <lib>.so<.number>, and don't produce dead links
if [[ -f libffi${SHLIB_EXT}.8 ]]; then
  ln -s libffi${SHLIB_EXT}.8 libffi${SHLIB_EXT}.7
  if [[ ! -f libffi.8{SHLIB_EXT} ]]; then
    ln -s libffi${SHLIB_EXT}.8 libffi.8${SHLIB_EXT}
  fi
fi
ln -s -f libffi.8${SHLIB_EXT} libffi.7${SHLIB_EXT}
popd

