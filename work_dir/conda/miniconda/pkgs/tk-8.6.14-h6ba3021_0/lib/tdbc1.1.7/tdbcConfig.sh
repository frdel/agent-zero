# tdbcConfig.sh --
#
# This shell script (for sh) is generated automatically by TDBC's configure
# script. It will create shell variables for most of the configuration options
# discovered by the configure script. This script is intended to be included
# by the configure scripts for TDBC extensions so that they don't have to
# figure this all out for themselves.
#
# The information in this file is specific to a single platform.
#
# RCS: @(#) $Id$

# TDBC's version number
tdbc_VERSION=1.1.7
TDBC_VERSION=1.1.7

# Name of the TDBC library - may be either a static or shared library
tdbc_LIB_FILE=libtdbc1.1.7.dylib
TDBC_LIB_FILE=libtdbc1.1.7.dylib

# String to pass to the linker to pick up the TDBC library from its build dir
tdbc_BUILD_LIB_SPEC="-L/private/var/folders/nz/j6p8yfhx1mv_0grj5xl4650h0000gp/T/abs_c2tv246l1c/croot/tk_1714770557340/work/tcl8.6.14/unix/pkgs/tdbc1.1.7 -ltdbc1.1.7"
TDBC_BUILD_LIB_SPEC="-L/private/var/folders/nz/j6p8yfhx1mv_0grj5xl4650h0000gp/T/abs_c2tv246l1c/croot/tk_1714770557340/work/tcl8.6.14/unix/pkgs/tdbc1.1.7 -ltdbc1.1.7"

# String to pass to the linker to pick up the TDBC library from its installed
# dir.
tdbc_LIB_SPEC="-L/var/folders/nz/j6p8yfhx1mv_0grj5xl4650h0000gp/T/abs_c2tv246l1c/croot/tk_1714770557340/_h_env_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_p/lib/tdbc1.1.7 -ltdbc1.1.7"
TDBC_LIB_SPEC="-L/var/folders/nz/j6p8yfhx1mv_0grj5xl4650h0000gp/T/abs_c2tv246l1c/croot/tk_1714770557340/_h_env_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_p/lib/tdbc1.1.7 -ltdbc1.1.7"

# Name of the TBDC stub library
tdbc_STUB_LIB_FILE="libtdbcstub1.1.7.a"
TDBC_STUB_LIB_FILE="libtdbcstub1.1.7.a"

# String to pass to the linker to pick up the TDBC stub library from its
# build directory
tdbc_BUILD_STUB_LIB_SPEC="-L/private/var/folders/nz/j6p8yfhx1mv_0grj5xl4650h0000gp/T/abs_c2tv246l1c/croot/tk_1714770557340/work/tcl8.6.14/unix/pkgs/tdbc1.1.7 -ltdbcstub1.1.7"
TDBC_BUILD_STUB_LIB_SPEC="-L/private/var/folders/nz/j6p8yfhx1mv_0grj5xl4650h0000gp/T/abs_c2tv246l1c/croot/tk_1714770557340/work/tcl8.6.14/unix/pkgs/tdbc1.1.7 -ltdbcstub1.1.7"

# String to pass to the linker to pick up the TDBC stub library from its
# installed directory
tdbc_STUB_LIB_SPEC="-L/var/folders/nz/j6p8yfhx1mv_0grj5xl4650h0000gp/T/abs_c2tv246l1c/croot/tk_1714770557340/_h_env_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_p/lib/tdbc1.1.7 -ltdbcstub1.1.7"
TDBC_STUB_LIB_SPEC="-L/var/folders/nz/j6p8yfhx1mv_0grj5xl4650h0000gp/T/abs_c2tv246l1c/croot/tk_1714770557340/_h_env_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_p/lib/tdbc1.1.7 -ltdbcstub1.1.7"

# Path name of the TDBC stub library in its build directory
tdbc_BUILD_STUB_LIB_PATH="/private/var/folders/nz/j6p8yfhx1mv_0grj5xl4650h0000gp/T/abs_c2tv246l1c/croot/tk_1714770557340/work/tcl8.6.14/unix/pkgs/tdbc1.1.7/libtdbcstub1.1.7.a"
TDBC_BUILD_STUB_LIB_PATH="/private/var/folders/nz/j6p8yfhx1mv_0grj5xl4650h0000gp/T/abs_c2tv246l1c/croot/tk_1714770557340/work/tcl8.6.14/unix/pkgs/tdbc1.1.7/libtdbcstub1.1.7.a"

# Path name of the TDBC stub library in its installed directory
tdbc_STUB_LIB_PATH="/var/folders/nz/j6p8yfhx1mv_0grj5xl4650h0000gp/T/abs_c2tv246l1c/croot/tk_1714770557340/_h_env_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_p/lib/tdbc1.1.7/libtdbcstub1.1.7.a"
TDBC_STUB_LIB_PATH="/var/folders/nz/j6p8yfhx1mv_0grj5xl4650h0000gp/T/abs_c2tv246l1c/croot/tk_1714770557340/_h_env_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_p/lib/tdbc1.1.7/libtdbcstub1.1.7.a"

# Location of the top-level source directories from which TDBC was built.
# This is the directory that contains doc/, generic/ and so on.  If TDBC
# was compiled in a directory other than the source directory, this still
# points to the location of the sources, not the location where TDBC was
# compiled.
tdbc_SRC_DIR="/private/var/folders/nz/j6p8yfhx1mv_0grj5xl4650h0000gp/T/abs_c2tv246l1c/croot/tk_1714770557340/work/tcl8.6.14/pkgs/tdbc1.1.7"
TDBC_SRC_DIR="/private/var/folders/nz/j6p8yfhx1mv_0grj5xl4650h0000gp/T/abs_c2tv246l1c/croot/tk_1714770557340/work/tcl8.6.14/pkgs/tdbc1.1.7"

# String to pass to the compiler so that an extension can find installed TDBC
# headers
tdbc_INCLUDE_SPEC="-I/var/folders/nz/j6p8yfhx1mv_0grj5xl4650h0000gp/T/abs_c2tv246l1c/croot/tk_1714770557340/_h_env_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_p/include"
TDBC_INCLUDE_SPEC="-I/var/folders/nz/j6p8yfhx1mv_0grj5xl4650h0000gp/T/abs_c2tv246l1c/croot/tk_1714770557340/_h_env_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_p/include"

# String to pass to the compiler so that an extension can find TDBC headers
# in the source directory
tdbc_BUILD_INCLUDE_SPEC="-I/private/var/folders/nz/j6p8yfhx1mv_0grj5xl4650h0000gp/T/abs_c2tv246l1c/croot/tk_1714770557340/work/tcl8.6.14/pkgs/tdbc1.1.7/generic"
TDBC_BUILD_INCLUDE_SPEC="-I/private/var/folders/nz/j6p8yfhx1mv_0grj5xl4650h0000gp/T/abs_c2tv246l1c/croot/tk_1714770557340/work/tcl8.6.14/pkgs/tdbc1.1.7/generic"

# Path name where .tcl files in the tdbc package appear at run time.
tdbc_LIBRARY_PATH="/var/folders/nz/j6p8yfhx1mv_0grj5xl4650h0000gp/T/abs_c2tv246l1c/croot/tk_1714770557340/_h_env_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_p/lib/tdbc1.1.7"
TDBC_LIBRARY_PATH="/var/folders/nz/j6p8yfhx1mv_0grj5xl4650h0000gp/T/abs_c2tv246l1c/croot/tk_1714770557340/_h_env_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_placehold_p/lib/tdbc1.1.7"

# Path name where .tcl files in the tdbc package appear at build time.
tdbc_BUILD_LIBRARY_PATH="/private/var/folders/nz/j6p8yfhx1mv_0grj5xl4650h0000gp/T/abs_c2tv246l1c/croot/tk_1714770557340/work/tcl8.6.14/pkgs/tdbc1.1.7/library"
TDBC_BUILD_LIBRARY_PATH="/private/var/folders/nz/j6p8yfhx1mv_0grj5xl4650h0000gp/T/abs_c2tv246l1c/croot/tk_1714770557340/work/tcl8.6.14/pkgs/tdbc1.1.7/library"

# Additional flags that must be passed to the C compiler to use tdbc
tdbc_CFLAGS=
TDBC_CFLAGS=

