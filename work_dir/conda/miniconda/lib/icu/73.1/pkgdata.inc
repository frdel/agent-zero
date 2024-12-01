GENCCODE_ASSEMBLY_TYPE=-a gcc-darwin
SO=dylib
SOBJ=dylib
A=a
LIBPREFIX=lib
LIB_EXT_ORDER=.73.1.dylib
COMPILE=arm64-apple-darwin20.0.0-clang -DU_ATTRIBUTE_DEPRECATED= -D_FORTIFY_SOURCE=2 -isystem /tmp/miniconda_temp/include -mmacosx-version-min=11.1   -DU_HAVE_STRTOD_L=1 -DU_HAVE_XLOCALE_H=1 -DU_HAVE_STRING_VIEW=1  -ftree-vectorize -fPIC -fPIE -fstack-protector-strong -O2 -pipe -isystem /tmp/miniconda_temp/include -fdebug-prefix-map=/var/folders/nz/j6p8yfhx1mv_0grj5xl4650h0000gp/T/abs_5f_fb0pad4/croot/icu_1692293050105/work=/usr/local/src/conda/icu-73.1 -fdebug-prefix-map=/tmp/miniconda_temp=/usr/local/src/conda-prefix -std=c11 -Wall -pedantic -Wshadow -Wpointer-arith -Wmissing-prototypes -Wwrite-strings   -fno-common -c
LIBFLAGS=-I/tmp/miniconda_temp/include  -dynamic
GENLIB=arm64-apple-darwin20.0.0-clang -dynamiclib -dynamic -ftree-vectorize -fPIC -fPIE -fstack-protector-strong -O2 -pipe -isystem /tmp/miniconda_temp/include -fdebug-prefix-map=/var/folders/nz/j6p8yfhx1mv_0grj5xl4650h0000gp/T/abs_5f_fb0pad4/croot/icu_1692293050105/work=/usr/local/src/conda/icu-73.1 -fdebug-prefix-map=/tmp/miniconda_temp=/usr/local/src/conda-prefix -std=c11 -Wall -pedantic -Wshadow -Wpointer-arith -Wmissing-prototypes -Wwrite-strings   -Wl,-pie -Wl,-headerpad_max_install_names -Wl,-dead_strip_dylibs -Wl,-rpath,/tmp/miniconda_temp/lib -L/tmp/miniconda_temp/lib -Wl,-rpath,/tmp/miniconda_temp/lib 
LDICUDTFLAGS=
LD_SONAME=-Wl,-compatibility_version -Wl,73 -Wl,-current_version -Wl,73.1 -install_name /tmp/miniconda_temp/lib/
RPATH_FLAGS=
BIR_LDFLAGS=
AR=arm64-apple-darwin20.0.0-ar
ARFLAGS=r -c
RANLIB=arm64-apple-darwin20.0.0-ranlib
INSTALL_CMD=/usr/bin/install -c
