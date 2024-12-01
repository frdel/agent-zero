#!/bin/bash

set -exuo pipefail

export TERM=xterm-256color

if [ `uname` == Linux ]; then
    ls $PREFIX/lib/libtinfow.so
fi

# Test libraries
ncurses_libraries=(
    "libncurses"
    "libtinfo"
    "libform"
    "libmenu"
    "libpanel"
)

for each_ncurses_library in "${ncurses_libraries[@]}"; do
    test -f ${PREFIX}/lib/"$each_ncurses_library".a
    test -f ${PREFIX}/lib/"$each_ncurses_library"w.a
    if [ `uname` == Linux ]; then
        test -f ${PREFIX}/lib/"$each_ncurses_library".so
        test -f ${PREFIX}/lib/"$each_ncurses_library"w.so
    elif [ `uname` == Darwin ]; then
        test -f ${PREFIX}/lib/"$each_ncurses_library".dylib
        test -f ${PREFIX}/lib/"$each_ncurses_library"w.dylib
    fi
done

# Test include directories
test -d ${PREFIX}/include/ncurses
test -d ${PREFIX}/include/ncursesw

# Test headers
ncurses_headers=(
    "curses.h"
    "cursesapp.h"
    "cursesf.h"
    "cursesm.h"
    "cursesp.h"
    "cursesw.h"
    "cursslk.h"
    "eti.h"
    "etip.h"
    "form.h"
    "menu.h"
    "nc_tparm.h"
    "ncurses.h"
    "ncurses_dll.h"
    "panel.h"
    "term.h"
    "term_entry.h"
    "termcap.h"
    "tic.h"
    "unctrl.h"
)

for each_ncurses_header in "${ncurses_headers[@]}"; do
    test -L ${PREFIX}/include/ncurses/"$each_ncurses_header"
    test -L ${PREFIX}/include/ncursesw/"$each_ncurses_header"
    test -f ${PREFIX}/include/"$each_ncurses_header"
done

# Test pkg-config files
ncurses_pc_files=(
    "form"
    "menu"
    "ncurses++"
    "ncurses"
    "panel"
    "tinfo"
)

for each_ncurses_pc_file in "${ncurses_pc_files[@]}"; do
    test -f ${PREFIX}/lib/pkgconfig/"$each_ncurses_pc_file"w.pc
    cat ${PREFIX}/lib/pkgconfig/"$each_ncurses_pc_file"w.pc
done

# Test ncurses library arguments.
#pkg-config ncurses --libs
pkg-config ncursesw --libs
pkg-config tinfow --libs
pkg-config ncurses++w --libs
pkg-config panelw --libs
pkg-config menuw --libs
pkg-config formw --libs
