

set -ex



test -f "${PREFIX}/bin/tclsh"
test -f "${PREFIX}/bin/wish"
test -f "${PREFIX}/bin/tclsh8.6"
test -f "${PREFIX}/bin/wish8.6"
test -f "${PREFIX}/include/tcl.h"
test -f "${PREFIX}/include/tclDecls.h"
test -f "${PREFIX}/include/tclPlatDecls.h"
test -f "${PREFIX}/include/tclPlatDecls.h"
test -f "${PREFIX}/include/tclTomMathDecls.h"
test -f "${PREFIX}/include/tclTomMath.h"
test -f "${PREFIX}/include/tk.h"
test -f "${PREFIX}/include/tkDecls.h"
test -f "${PREFIX}/include/tkPlatDecls.h"
test -f "${PREFIX}/lib/libtcl8.6.dylib"
test -f "${PREFIX}/lib/libtclstub8.6.a"
test -f "${PREFIX}/lib/libtk8.6.dylib"
test -f "${PREFIX}/lib/libtkstub8.6.a"
tclsh hello.tcl
tclsh8.6 hello.tcl
wish hello.tcl
wish8.6 hello.tcl
exit 0
