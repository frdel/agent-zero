#!/bin/bash
echo "Building ${PKG_NAME}."

cd build

# Installing
echo "Installing..."
ninja install || exit 1

if [[ "$PKG_NAME" == *static ]]
then
    # relying on conda to dedup package
    echo "Doing nothing"
else
    rm -rf ${PREFIX}/lib/*a
fi
