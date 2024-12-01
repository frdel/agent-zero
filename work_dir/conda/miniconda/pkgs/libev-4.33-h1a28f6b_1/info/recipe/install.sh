#!/usr/bin/env bash

make install

if [[ "$PKG_NAME" == *static ]]; then
	# relying on conda to dedup package
	echo "Keeping all files, conda will dedupe"
else
	rm -rf ${PREFIX}/lib/libev.a
fi

if [[ "$PKG_NAME" != *-libevent ]]; then
	rm "${PREFIX}/include/event.h"
fi
