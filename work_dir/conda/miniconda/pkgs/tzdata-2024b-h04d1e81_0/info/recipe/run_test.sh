#!/usr/bin/env bash
# Run the tests for tzdata

set -ex

exists() {
	FULL_PATH="${PREFIX}/${1}"
	if [ -f "${FULL_PATH}" ]; then
		echo "Found ${1}"
	else
		echo "Could not find ${FULL_PATH}"
		exit 1
	fi
}

for i in share/zoneinfo/{zone,iso3166,zone1970}.tab share/zoneinfo/leapseconds share/zoneinfo/tzdata.zi; do
	exists $i
done

# Make sure we only package zoneinfo and nothing else.
dirs="$(find "${PREFIX}" -mindepth 1 -maxdepth 2 ! -path "${PREFIX}/share" ! -path "${PREFIX}/conda-meta*")"
test "${dirs}" = "${PREFIX}/share/zoneinfo"

# Make sure we only package timezone information files.
if [ `uname` == 'Darwin' ]; then
  # OSX does not have the '-printf' operator.
  heads="$(find "${PREFIX}/share/zoneinfo" -type f ! -name "*.zi" ! -name "*.tab" ! -name leapseconds -exec head -c4 {} ';' -print0 | uniq | cut -c1-4)"
else
  heads="$(find "${PREFIX}/share/zoneinfo" -type f ! -name "*.zi" ! -name "*.tab" ! -name leapseconds -exec head -c4 {} ';' -printf \\n | uniq)"
fi
test "${heads}" = TZif
