set -xe

if [[ $(uname) == Darwin ]]; then
  export CONDA_BUILD_SYSROOT_TEMP="-isysroot $(xcrun --show-sdk-path)"
else
  export CONDA_BUILD_SYSROOT_TEMP=
fi

export PATH=$PREFIX/bin:$PATH
LINK_FLAGS=" $CONDA_BUILD_SYSROOT_TEMP -Wl,-rpath,$PREFIX/lib -L$PREFIX/lib -Wl,-v -v"

if [[ $(uname) == Darwin ]]; then
    llvm-nm $PREFIX/lib/libc++.1.dylib
else
    LINK_FLAGS="${LINK_FLAGS} -lc++abi"
fi

FILES=test_sources/*.c
for f in $FILES
do
    clang -O2 -g $f ${LINK_FLAGS}
    ./a.out
done

FILES=test_sources/*.cpp
for f in $FILES
do
    clang++ -stdlib=libc++ -O2 -g $f $LINK_FLAGS
    ./a.out
done

FILES=test_sources/cpp11/*.cpp
for f in $FILES
do
    clang++ -stdlib=libc++ -std=c++11 -O2 -g $f $LINK_FLAGS
    ./a.out
done

FILES=test_sources/cpp14/*.cpp
for f in $FILES
do
    clang++ -stdlib=libc++ -std=c++14 -O2 -g $f $LINK_FLAGS
    ./a.out
done
