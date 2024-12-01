#!/bin/bash

if [[ $PKG_NAME == "mamba" ]]; then
    cd mamba || exit 1
    $PYTHON -m pip install . --no-deps --no-build-isolation -v
    
    echo "Adding link to mamba into condabin";
    mkdir -p $PREFIX/condabin
    ln -s $PREFIX/bin/mamba $PREFIX/condabin/mamba
    
    exit 0
fi

rm -rf build
mkdir build
cd build || exit 1

export CXXFLAGS="${CXXFLAGS} -D_LIBCPP_DISABLE_AVAILABILITY=1"

# Generate the build files.
echo "Generating the build files..."

if [[ $PKG_NAME == "libmamba" ]]; then
    cmake .. ${CMAKE_ARGS}              \
    -GNinja                         \
    -DCMAKE_INSTALL_PREFIX=$PREFIX  \
    -DCMAKE_PREFIX_PATH=$PREFIX     \
    -DCMAKE_BUILD_TYPE=Release      \
    -DBUILD_LIBMAMBA=ON             \
    -DBUILD_SHARED=ON               \
    -DBUILD_MAMBA_PACKAGE=ON
    elif [[ $PKG_NAME == "libmambapy" ]]; then
    # TODO finds wrong python interpreter!!!!
    cmake .. ${CMAKE_ARGS}              \
    -GNinja                         \
    -DCMAKE_PREFIX_PATH=$PREFIX     \
    -DCMAKE_INSTALL_PREFIX=$PREFIX  \
    -DCMAKE_BUILD_TYPE=Release      \
    -DPython_EXECUTABLE=$PYTHON     \
    -DBUILD_LIBMAMBAPY=ON
fi

# Build.
echo "Building..."
ninja || exit 1

# Installing
echo "Installing..."
ninja install || exit 1

if [[ $PKG_NAME == "libmambapy" ]]; then
    cd ../libmambapy || exit 1
    rm -rf build
    $PYTHON -m pip install . --no-deps --no-build-isolation -v
    find libmambapy/bindings* -type f -print0 | xargs -0 rm -f --
fi

# Error free exit!
echo "Error free exit!"
exit 0
