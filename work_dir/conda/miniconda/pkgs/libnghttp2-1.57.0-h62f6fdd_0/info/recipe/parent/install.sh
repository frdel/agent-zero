#!/bin/bash

make install

if [[ "$PKG_NAME" == *static ]]
then
    rm -rfv ${PREFIX}/bin/*
else
    rm -rfv ${PREFIX}/lib/*.a
fi
