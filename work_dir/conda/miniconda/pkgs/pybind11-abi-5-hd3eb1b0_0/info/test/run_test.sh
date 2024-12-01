

set -ex



matched=false; while read -r version; do [ "$version" -eq "5" ] && { matched=true; break; }; done < <(awk '/define PYBIND11_INTERNALS_VERSION/{print $NF}' include/pybind11/detail/internals.h); [ "$matched" = true ] && exit 0 || exit 1
exit 0
