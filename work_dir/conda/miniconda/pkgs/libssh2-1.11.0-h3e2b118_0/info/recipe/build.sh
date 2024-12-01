#!/bin/bash

if [[ $target_platform =~ linux.* ]]; then
  export LDFLAGS="$LDFLAGS -Wl,-rpath-link,$PREFIX/lib"
fi

# linux-aarch64 activations fails to set `ar` tool. This can be
# removed when ctng-compiler-activation is corrected.
if [[ "${target_platform}" == linux-aarch64 ]]; then
  if [[ -n "$AR" ]]; then
      CMAKE_ARGS="${CMAKE_ARGS} -DCMAKE_AR=${AR}"
  fi
fi

mkdir build-shared
pushd build-shared || exit
  cmake -GNinja  \
        ${CMAKE_ARGS}                     \
        -DCMAKE_INSTALL_PREFIX=${PREFIX}  \
        -DBUILD_SHARED_LIBS=ON            \
        -DBUILD_STATIC_LIBS=OFF           \
        -DCMAKE_INSTALL_LIBDIR=lib        \
        -DCRYPTO_BACKEND=OpenSSL          \
        -DENABLE_ZLIB_COMPRESSION=ON      \
        -DBUILD_EXAMPLES=OFF              \
        -DBUILD_TESTING=ON                \
        -DRUN_DOCKER_TESTS=OFF            \
        -DRUN_SSHD_TESTS=OFF              \
        ..

  ninja -j${CPU_COUNT}
  # Skip Docker and SSHD tests (see above) because they involve external dependencies
  ctest --output-on-failure
  ninja install
  # ctest fails on the docker image 'sh: docker: command not found'
popd || exit
