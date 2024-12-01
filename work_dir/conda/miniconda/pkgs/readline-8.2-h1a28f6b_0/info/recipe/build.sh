#!/usr/bin/env bash

./configure --prefix=${PREFIX}  \
            --build=${BUILD}    \
            --host=${HOST}      \
            --enable-multibyte  \
            --with-curses       \
            --disable-install-examples  \
            || { cat config.log; exit 1; }
make SHLIB_LIBS="$(pkg-config --libs ncursesw)" -j${CPU_COUNT} ${VERBOSE_AT}
make install
