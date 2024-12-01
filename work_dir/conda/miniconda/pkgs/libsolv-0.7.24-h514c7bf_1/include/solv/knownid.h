/*
 * Copyright (c) 2007-2014, Novell Inc.
 *
 * This program is licensed under the BSD license, read LICENSE.BSD
 * for further information
 */

/*
 * knownid.h
 *
 */

/*
 * Warning: you're free to append new entries, but insert/delete breaks
 * the ABI!
 */

#ifndef LIBSOLV_KNOWNID_H
#define LIBSOLV_KNOWNID_H

#undef KNOWNID
#ifdef KNOWNID_INITIALIZE
# define KNOWNID(a, b) b
static const char *initpool_data[] = {
#else
# define KNOWNID(a, b) a
enum solv_knownid {
#endif

KNOWNID(ID_NULL,			"<NULL>"),
KNOWNID(ID_EMPTY,			""),

/* The following Ids are stored in the solvable and must
 * come in one block */
KNOWNID(SOLVABLE_NAME,			"solvable:name"),
KNOWNID(SOLVABLE_ARCH,			"solvable:arch"),
KNOWNID(SOLVABLE_EVR,			"solvable:evr"),
KNOWNID(SOLVABLE_VENDOR,		"solvable:vendor"),
KNOWNID(SOLVABLE_PROVIDES,		"solvable:provides"),
KNOWNID(SOLVABLE_OBSOLETES,		"solvable:obsoletes"),
KNOWNID(SOLVABLE_CONFLICTS,		"solvable:conflicts"),
KNOWNID(SOLVABLE_REQUIRES,		"solvable:requires"),
KNOWNID(SOLVABLE_RECOMMENDS,		"solvable:recommends"),
KNOWNID(SOLVABLE_SUGGESTS,		"solvable:suggests"),
KNOWNID(SOLVABLE_SUPPLEMENTS,		"solvable:supplements"),
KNOWNID(SOLVABLE_ENHANCES,		"solvable:enhances"),
KNOWNID(RPM_RPMDBID,			"rpm:dbid"),

/* normal requires before this, prereqs after this */
KNOWNID(SOLVABLE_PREREQMARKER,		"solvable:prereqmarker"),
/* normal provides before this, generated file provides after this */
KNOWNID(SOLVABLE_FILEMARKER,		"solvable:filemarker"),

KNOWNID(NAMESPACE_INSTALLED,		"namespace:installed"),
KNOWNID(NAMESPACE_MODALIAS,		"namespace:modalias"),
KNOWNID(NAMESPACE_SPLITPROVIDES,	"namespace:splitprovides"),
KNOWNID(NAMESPACE_LANGUAGE,		"namespace:language"),
KNOWNID(NAMESPACE_FILESYSTEM,		"namespace:filesystem"),
KNOWNID(NAMESPACE_OTHERPROVIDERS,	"namespace:otherproviders"),

KNOWNID(SYSTEM_SYSTEM,			"system:system"),

/* special solvable architectures */
KNOWNID(ARCH_SRC,			"src"),
KNOWNID(ARCH_NOSRC,			"nosrc"),
KNOWNID(ARCH_NOARCH,			"noarch"),
KNOWNID(ARCH_ALL,			"all"),
KNOWNID(ARCH_ANY,			"any"),

/* the meta tags used in solv file storage */
KNOWNID(REPOSITORY_SOLVABLES,		"repository:solvables"),
KNOWNID(REPOSITORY_DELTAINFO,		"repository:deltainfo"),

/* sub-repository information, they will get loaded on demand */
KNOWNID(REPOSITORY_EXTERNAL,		"repository:external"),
KNOWNID(REPOSITORY_KEYS,		"repository:keys"),
KNOWNID(REPOSITORY_LOCATION,		"repository:location"),

/* the known data types */
KNOWNID(REPOKEY_TYPE_VOID,		"repokey:type:void"),
KNOWNID(REPOKEY_TYPE_CONSTANT,		"repokey:type:constant"),
KNOWNID(REPOKEY_TYPE_CONSTANTID,	"repokey:type:constantid"),
KNOWNID(REPOKEY_TYPE_ID,		"repokey:type:id"),
KNOWNID(REPOKEY_TYPE_NUM,		"repokey:type:num"),
KNOWNID(REPOKEY_TYPE_DIR,		"repokey:type:dir"),
KNOWNID(REPOKEY_TYPE_STR,		"repokey:type:str"),
KNOWNID(REPOKEY_TYPE_BINARY,		"repokey:type:binary"),
KNOWNID(REPOKEY_TYPE_IDARRAY,		"repokey:type:idarray"),
KNOWNID(REPOKEY_TYPE_REL_IDARRAY,	"repokey:type:relidarray"),
KNOWNID(REPOKEY_TYPE_DIRSTRARRAY,	"repokey:type:dirstrarray"),
KNOWNID(REPOKEY_TYPE_DIRNUMNUMARRAY,	"repokey:type:dirnumnumarray"),
KNOWNID(REPOKEY_TYPE_MD5,		"repokey:type:md5"),
KNOWNID(REPOKEY_TYPE_SHA1,		"repokey:type:sha1"),
KNOWNID(REPOKEY_TYPE_SHA224,		"repokey:type:sha224"),
KNOWNID(REPOKEY_TYPE_SHA256,		"repokey:type:sha256"),
KNOWNID(REPOKEY_TYPE_SHA384,		"repokey:type:sha384"),
KNOWNID(REPOKEY_TYPE_SHA512,		"repokey:type:sha512"),
KNOWNID(REPOKEY_TYPE_FIXARRAY,		"repokey:type:fixarray"),
KNOWNID(REPOKEY_TYPE_FLEXARRAY,		"repokey:type:flexarray"),
KNOWNID(REPOKEY_TYPE_DELETED,		"repokey:type:deleted"),	/* internal only */

KNOWNID(SOLVABLE_SUMMARY,		"solvable:summary"),
KNOWNID(SOLVABLE_DESCRIPTION,		"solvable:description"),
KNOWNID(SOLVABLE_DISTRIBUTION,		"solvable:distribution"),
KNOWNID(SOLVABLE_AUTHORS,		"solvable:authors"),
KNOWNID(SOLVABLE_PACKAGER,		"solvable:packager"),
KNOWNID(SOLVABLE_GROUP,			"solvable:group"),
KNOWNID(SOLVABLE_URL,			"solvable:url"),
KNOWNID(SOLVABLE_KEYWORDS,		"solvable:keywords"),
KNOWNID(SOLVABLE_LICENSE,		"solvable:license"),
KNOWNID(SOLVABLE_BUILDTIME,		"solvable:buildtime"),
KNOWNID(SOLVABLE_BUILDHOST,		"solvable:buildhost"),
KNOWNID(SOLVABLE_EULA,			"solvable:eula"),
KNOWNID(SOLVABLE_CPEID,		        "solvable:cpeid"),
KNOWNID(SOLVABLE_MESSAGEINS,		"solvable:messageins"),
KNOWNID(SOLVABLE_MESSAGEDEL,		"solvable:messagedel"),
KNOWNID(SOLVABLE_INSTALLSIZE,		"solvable:installsize"),
KNOWNID(SOLVABLE_DISKUSAGE,		"solvable:diskusage"),
KNOWNID(SOLVABLE_FILELIST,		"solvable:filelist"),
KNOWNID(SOLVABLE_INSTALLTIME,		"solvable:installtime"),
KNOWNID(SOLVABLE_MEDIADIR,		"solvable:mediadir"),
KNOWNID(SOLVABLE_MEDIAFILE,		"solvable:mediafile"),
KNOWNID(SOLVABLE_MEDIANR,		"solvable:medianr"),
KNOWNID(SOLVABLE_MEDIABASE,		"solvable:mediabase"),	/* <location xml:base=... > */
KNOWNID(SOLVABLE_DOWNLOADSIZE,		"solvable:downloadsize"),
KNOWNID(SOLVABLE_SOURCEARCH,		"solvable:sourcearch"),
KNOWNID(SOLVABLE_SOURCENAME,		"solvable:sourcename"),
KNOWNID(SOLVABLE_SOURCEEVR,		"solvable:sourceevr"),
KNOWNID(SOLVABLE_ISVISIBLE,		"solvable:isvisible"),
KNOWNID(SOLVABLE_TRIGGERS,		"solvable:triggers"),
KNOWNID(SOLVABLE_CHECKSUM,		"solvable:checksum"),
KNOWNID(SOLVABLE_PKGID,			"solvable:pkgid"),	/* pkgid: md5sum over header + payload */
KNOWNID(SOLVABLE_HDRID,			"solvable:hdrid"),	/* hdrid: sha1sum over header only */
KNOWNID(SOLVABLE_LEADSIGID,		"solvable:leadsigid"),  /* leadsigid: md5sum over lead + sigheader */

KNOWNID(SOLVABLE_PATCHCATEGORY,		"solvable:patchcategory"),
KNOWNID(SOLVABLE_HEADEREND,		"solvable:headerend"),
KNOWNID(SOLVABLE_CHANGELOG,		"solvable:changelog"),
KNOWNID(SOLVABLE_CHANGELOG_AUTHOR,	"solvable:changelog:author"),
KNOWNID(SOLVABLE_CHANGELOG_TIME,	"solvable:changelog:time"),
KNOWNID(SOLVABLE_CHANGELOG_TEXT,	"solvable:changelog:text"),
KNOWNID(SOLVABLE_INSTALLSTATUS,		"solvable:installstatus"),	/* debian install status */
KNOWNID(SOLVABLE_PREREQ_IGNOREINST,	"solvable:prereq_ignoreinst"),	/* ignore these pre-requires for installed packages */

/* stuff for solvables of type pattern */
KNOWNID(SOLVABLE_CATEGORY,		"solvable:category"),
KNOWNID(SOLVABLE_INCLUDES,		"solvable:includes"),
KNOWNID(SOLVABLE_EXTENDS,		"solvable:extends"),
KNOWNID(SOLVABLE_ICON,			"solvable:icon"),
KNOWNID(SOLVABLE_ORDER,			"solvable:order"),

/* extra definitions for updates (i.e. patch: solvables) */
KNOWNID(UPDATE_REBOOT,			"update:reboot"),	/* reboot suggested (kernel update) */
KNOWNID(UPDATE_RESTART,			"update:restart"),	/* restart suggested (update stack update) */
KNOWNID(UPDATE_RELOGIN,			"update:relogin"),	/* relogin suggested */

KNOWNID(UPDATE_MESSAGE,			"update:message"),	/* informative message */
KNOWNID(UPDATE_SEVERITY,		"update:severity"),	/* "Important", ...*/
KNOWNID(UPDATE_RIGHTS,			"update:rights"),	/* copyright */

/* 'content' of patch, usually list of packages */
KNOWNID(UPDATE_COLLECTION,		"update:collection"),          /*  "name evr arch" */
KNOWNID(UPDATE_COLLECTION_NAME,		"update:collection:name"),     /*   name */
KNOWNID(UPDATE_COLLECTION_EVR,		"update:collection:evr"),      /*   epoch:version-release */
KNOWNID(UPDATE_COLLECTION_ARCH,		"update:collection:arch"),     /*   architecture */
KNOWNID(UPDATE_COLLECTION_FILENAME,	"update:collection:filename"), /*   filename (of rpm) */
KNOWNID(UPDATE_COLLECTION_FLAGS,	"update:collection:flags"),    /*   reboot(1)/restart(2) suggested if this rpm gets updated */

KNOWNID(UPDATE_REFERENCE,		"update:reference"),		/* external references for the update */
KNOWNID(UPDATE_REFERENCE_TYPE,		"update:reference:type"),	/*  type, e.g. 'bugzilla' or 'cve' */
KNOWNID(UPDATE_REFERENCE_HREF,		"update:reference:href"),	/*  href, e.g. 'http://bugzilla...' */
KNOWNID(UPDATE_REFERENCE_ID,		"update:reference:id"),		/*  id, e.g. bug number */
KNOWNID(UPDATE_REFERENCE_TITLE,		"update:reference:title"),	/*  title, e.g. "the bla forz scribs on fuggle" */

/* extra definitions for products */
KNOWNID(PRODUCT_REFERENCEFILE,		"product:referencefile"),	/* installed product only */
KNOWNID(PRODUCT_SHORTLABEL,		"product:shortlabel"),		/* not in repomd? */
KNOWNID(PRODUCT_DISTPRODUCT,		"product:distproduct"),		/* obsolete */
KNOWNID(PRODUCT_DISTVERSION,		"product:distversion"),		/* obsolete */
KNOWNID(PRODUCT_TYPE,			"product:type"),		/* e.g. 'base' */
KNOWNID(PRODUCT_URL,			"product:url"),
KNOWNID(PRODUCT_URL_TYPE,		"product:url:type"),
KNOWNID(PRODUCT_FLAGS,			"product:flags"),		/* e.g. 'update', 'no_you' */
KNOWNID(PRODUCT_PRODUCTLINE,		"product:productline"),		/* installed product only */
KNOWNID(PRODUCT_REGISTER_TARGET,	"product:regtarget"),		/* installed and available product */
KNOWNID(PRODUCT_REGISTER_FLAVOR,	"product:regflavor"),		/* installed and available product */
KNOWNID(PRODUCT_REGISTER_RELEASE,	"product:regrelease"),		/* installed product only */
KNOWNID(PRODUCT_UPDATES_REPOID,	        "product:updates:repoid"),
KNOWNID(PRODUCT_UPDATES,	        "product:updates"),
KNOWNID(PRODUCT_ENDOFLIFE,	        "product:endoflife"),

/* argh, should rename to repository and unify with REPOMD */
KNOWNID(SUSETAGS_DATADIR,		"susetags:datadir"),
KNOWNID(SUSETAGS_DESCRDIR,		"susetags:descrdir"),
KNOWNID(SUSETAGS_DEFAULTVENDOR,		"susetags:defaultvendor"),
KNOWNID(SUSETAGS_FILE,			"susetags:file"),
KNOWNID(SUSETAGS_FILE_NAME,		"susetags:file:name"),
KNOWNID(SUSETAGS_FILE_TYPE,		"susetags:file:type"),
KNOWNID(SUSETAGS_FILE_CHECKSUM,		"susetags:file:checksum"),
KNOWNID(SUSETAGS_SHARE_NAME,		"susetags:share:name"),
KNOWNID(SUSETAGS_SHARE_EVR,		"susetags:share:evr"),
KNOWNID(SUSETAGS_SHARE_ARCH,		"susetags:share:arch"),

KNOWNID(REPOSITORY_ADDEDFILEPROVIDES,	"repository:addedfileprovides"),	/* file provides already added to our solvables */
KNOWNID(REPOSITORY_RPMDBCOOKIE,		"repository:rpmdbcookie"),	/* inode of the rpm database for rpm --rebuilddb detection */
KNOWNID(REPOSITORY_FILTEREDFILELIST,	"repository:filteredfilelist"),	/* filelist in repository is filtered */
KNOWNID(REPOSITORY_TIMESTAMP,		"repository:timestamp"),	/* timestamp then the repository was generated */
KNOWNID(REPOSITORY_EXPIRE,		"repository:expire"),		/* hint when the metadata could be outdated w/respect to generated timestamp */
KNOWNID(REPOSITORY_UPDATES,		"repository:updates"),		/* which things does this repo provides updates for, if it does (array) (obsolete?) */
KNOWNID(REPOSITORY_DISTROS,		"repository:distros"),		/* which products this repository is supposed to be for (array) */
KNOWNID(REPOSITORY_PRODUCT_LABEL,       "repository:product:label"),
KNOWNID(REPOSITORY_PRODUCT_CPEID,	"repository:product:cpeid"),
KNOWNID(REPOSITORY_REPOID,		"repository:repoid"),		/* obsolete? */
KNOWNID(REPOSITORY_KEYWORDS,		"repository:keywords"),		/* keyword (tags) for this repository */
KNOWNID(REPOSITORY_REVISION,		"repository:revision"),		/* revision of the repository. arbitrary string */
KNOWNID(REPOSITORY_TOOLVERSION,		"repository:toolversion"),

KNOWNID(DELTA_PACKAGE_NAME,		"delta:pkgname"),
KNOWNID(DELTA_PACKAGE_EVR,		"delta:pkgevr"),
KNOWNID(DELTA_PACKAGE_ARCH,		"delta:pkgarch"),
KNOWNID(DELTA_LOCATION_DIR,		"delta:locdir"),
KNOWNID(DELTA_LOCATION_NAME,		"delta:locname"),
KNOWNID(DELTA_LOCATION_EVR,		"delta:locevr"),
KNOWNID(DELTA_LOCATION_SUFFIX,		"delta:locsuffix"),
KNOWNID(DELTA_DOWNLOADSIZE,		"delta:downloadsize"),
KNOWNID(DELTA_CHECKSUM,			"delta:checksum"),
KNOWNID(DELTA_BASE_EVR,			"delta:baseevr"),
KNOWNID(DELTA_SEQ_NAME,			"delta:seqname"),
KNOWNID(DELTA_SEQ_EVR,			"delta:seqevr"),
KNOWNID(DELTA_SEQ_NUM,			"delta:seqnum"),
KNOWNID(DELTA_LOCATION_BASE,	        "delta:locbase"),	/* <location xml:base=... > */

KNOWNID(REPOSITORY_REPOMD,		"repository:repomd"),
KNOWNID(REPOSITORY_REPOMD_TYPE,		"repository:repomd:type"),
KNOWNID(REPOSITORY_REPOMD_LOCATION,	"repository:repomd:location"),
KNOWNID(REPOSITORY_REPOMD_TIMESTAMP,	"repository:repomd:timestamp"),
KNOWNID(REPOSITORY_REPOMD_CHECKSUM,	"repository:repomd:checksum"),
KNOWNID(REPOSITORY_REPOMD_OPENCHECKSUM,	"repository:repomd:openchecksum"),
KNOWNID(REPOSITORY_REPOMD_SIZE,		"repository:repomd:size"),

KNOWNID(PUBKEY_KEYID,		        "pubkey:keyid"),
KNOWNID(PUBKEY_FINGERPRINT,	        "pubkey:fingerprint"),
KNOWNID(PUBKEY_EXPIRES,		        "pubkey:expires"),
KNOWNID(PUBKEY_SIGNATURES,	        "pubkey:signatures"),
KNOWNID(PUBKEY_DATA,		        "pubkey:data"),
KNOWNID(PUBKEY_SUBKEYOF,	        "pubkey:subkeyof"),

KNOWNID(SIGNATURE_ISSUER,	        "signature:issuer"),
KNOWNID(SIGNATURE_TIME,	        	"signature:time"),
KNOWNID(SIGNATURE_EXPIRES,	        "signature:expires"),
KNOWNID(SIGNATURE_DATA,		        "signature:data"),

/* 'content' of patch, usually list of modules */
KNOWNID(UPDATE_MODULE,			"update:module"),		/* "name stream version context arch" */
KNOWNID(UPDATE_MODULE_NAME,		"update:module:name"),		/* name */
KNOWNID(UPDATE_MODULE_STREAM,		"update:module:stream"),	/* stream */
KNOWNID(UPDATE_MODULE_VERSION,		"update:module:version"),	/* version */
KNOWNID(UPDATE_MODULE_CONTEXT,		"update:module:context"),	/* context */
KNOWNID(UPDATE_MODULE_ARCH,		"update:module:arch"),		/* architecture */

KNOWNID(SOLVABLE_BUILDVERSION,		"solvable:buildversion"),	/* conda */
KNOWNID(SOLVABLE_BUILDFLAVOR,		"solvable:buildflavor"),	/* conda */

KNOWNID(UPDATE_STATUS,			"update:status"),		/* "stable", "testing", ...*/

KNOWNID(LIBSOLV_SELF_DESTRUCT_PKG,      "libsolv-self-destruct-pkg()"),	/* this package will self-destruct on installation */

KNOWNID(SOLVABLE_CONSTRAINS,		"solvable:constrains"),		/* conda */
KNOWNID(SOLVABLE_TRACK_FEATURES,	"solvable:track_features"),	/* conda */
KNOWNID(SOLVABLE_ISDEFAULT,		"solvable:isdefault"),
KNOWNID(SOLVABLE_LANGONLY,		"solvable:langonly"),

KNOWNID(UPDATE_COLLECTIONLIST,		"update:collectionlist"),	/* list of UPDATE_COLLECTION (actually packages) and UPDATE_MODULE */
KNOWNID(SOLVABLE_MULTIARCH,		"solvable:multiarch"),		/* debian multi-arch field */
KNOWNID(SOLVABLE_SIGNATUREDATA,		"solvable:signaturedata"),	/* conda */

KNOWNID(ID_NUM_INTERNAL,		0)

#ifdef KNOWNID_INITIALIZE
};
#else
};
#endif

#undef KNOWNID

#endif


