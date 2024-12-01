/*
 * Copyright (c) 2016, SUSE LLC
 *
 * This program is licensed under the BSD license, read LICENSE.BSD
 * for further information
 */

/*
 * solvversion.h
 * 
 */

#ifndef LIBSOLV_SOLVVERSION_H
#define LIBSOLV_SOLVVERSION_H

#define LIBSOLV_VERSION_STRING "0.7.24"
#define LIBSOLV_VERSION_MAJOR 0
#define LIBSOLV_VERSION_MINOR 7
#define LIBSOLV_VERSION_PATCH 24
#define LIBSOLV_VERSION (LIBSOLV_VERSION_MAJOR * 10000 + LIBSOLV_VERSION_MINOR * 100 + LIBSOLV_VERSION_PATCH)

extern const char solv_version[];
extern int solv_version_major;
extern int solv_version_minor;
extern int solv_version_patch;
extern const char solv_toolversion[];

/* #undef LIBSOLV_FEATURE_LINKED_PKGS */
/* #undef LIBSOLV_FEATURE_COMPLEX_DEPS */
#define LIBSOLV_FEATURE_MULTI_SEMANTICS
#define LIBSOLV_FEATURE_CONDA

#define LIBSOLVEXT_FEATURE_PCRE2
/* #undef LIBSOLVEXT_FEATURE_RPMPKG */
/* #undef LIBSOLVEXT_FEATURE_RPMDB */
/* #undef LIBSOLVEXT_FEATURE_RPMDB_BYRPMHEADER */
/* #undef LIBSOLVEXT_FEATURE_PUBKEY */
/* #undef LIBSOLVEXT_FEATURE_RPMMD */
/* #undef LIBSOLVEXT_FEATURE_SUSEREPO */
/* #undef LIBSOLVEXT_FEATURE_COMPS */
/* #undef LIBSOLVEXT_FEATURE_HELIXREPO */
/* #undef LIBSOLVEXT_FEATURE_DEBIAN */
/* #undef LIBSOLVEXT_FEATURE_ARCHREPO */
/* #undef LIBSOLVEXT_FEATURE_HAIKU */
/* #undef LIBSOLVEXT_FEATURE_APPDATA */
#define LIBSOLVEXT_FEATURE_ZLIB_COMPRESSION
/* #undef LIBSOLVEXT_FEATURE_LZMA_COMPRESSION */
/* #undef LIBSOLVEXT_FEATURE_BZIP2_COMPRESSION */
/* #undef LIBSOLVEXT_FEATURE_ZSTD_COMPRESSION */
/* #undef LIBSOLVEXT_FEATURE_ZCHUNK_COMPRESSION */

/* see tools/common_write.c for toolversion history */
#define LIBSOLV_TOOLVERSION "1.2"

#endif
