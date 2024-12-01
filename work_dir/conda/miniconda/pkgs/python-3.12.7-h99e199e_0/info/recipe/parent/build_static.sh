#!/bin/bash
set -ex

cd ${SRC_DIR}

_buildd_static=build-static
_buildd_shared=build-shared
if [[ ${DEBUG_PY} == yes ]]; then
  DBG=d
else
  DBG=
fi
VER=${PKG_VERSION%.*}
VERABI=${VER}${DBG}

case "$target_platform" in
  linux-64)
    OLD_HOST=$(echo ${HOST} | sed -e 's/-conda_cos6//g')
    OLD_HOST=$(echo ${OLD_HOST} | sed -e 's/-conda_cos7//g')
    OLD_HOST=$(echo ${OLD_HOST} | sed -e 's/-conda//g')
    ;;
  linux-*)
    OLD_HOST=$(echo ${HOST} | sed -e 's/-conda_cos7//g')
    OLD_HOST=$(echo ${OLD_HOST} | sed -e 's/-conda//g')
    ;;
  *)
    OLD_HOST=$HOST
    ;;
esac

cp -pf ${_buildd_static}/libpython${VERABI}.a ${PREFIX}/lib/libpython${VERABI}.a
if [[ ${HOST} =~ .*linux.* ]]; then
  pushd ${PREFIX}/lib/python${VERABI}/config-${VERABI}-${OLD_HOST}
elif [[ ${HOST} =~ .*darwin.* ]]; then
  pushd ${PREFIX}/lib/python${VERABI}/config-${VERABI}-darwin
fi
ln -s ../../libpython${VERABI}.a libpython${VERABI}.a
popd
# If the LTO info in the normal lib is problematic (using different compilers for example
# we also provide a 'nolto' version).
cp -pf ${_buildd_shared}/libpython${VERABI}-pic.a ${PREFIX}/lib/libpython${VERABI}.nolto.a
