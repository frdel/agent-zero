# FindLibSolv - Find libsolv headers and libraries.
#
# Sample:
#
#   SET( LibSolv_USE_STATIC_LIBS OFF )
#   FIND_PACKAGE( LibSolv REQUIRED ext )
#   IF( LibSolv_FOUND )
#      INCLUDE_DIRECTORIES( ${LibSolv_INCLUDE_DIRS} )
#      TARGET_LINK_LIBRARIES( ... ${LibSolv_LIBRARIES} )
#   ENDIF()
#
# Variables used by this module need to be set before calling find_package
# (not that they are cmale cased like the modiulemane itself):
#
#   LibSolv_USE_STATIC_LIBS	Can be set to ON to force the use of the static
#				libsolv libraries. Defaults to OFF.
#
# Supported components:
#
#   ext				Also include libsolvext
#
# Variables provided by this module:
#
#   LibSolv_FOUND		Include dir, libsolv and all extra libraries
#				specified in the COMPONENTS list were found.
#
#   LibSolv_LIBRARIES		Link to these to use all the libraries you specified.
#
#   LibSolv_INCLUDE_DIRS	Include directories.
#
# For each component you specify in find_package(), the following (UPPER-CASE)
# variables are set to pick and choose components instead of just using LibSolv_LIBRARIES:
#
#   LIBSOLV_FOUND			TRUE if libsolv was found
#   LIBSOLV_LIBRARY			libsolv libraries
#
#   LIBSOLV_${COMPONENT}_FOUND		TRUE if the library component was found
#   LIBSOLV_${COMPONENT}_LIBRARY	The libraries for the specified component
#

# Support preference of static libs by adjusting CMAKE_FIND_LIBRARY_SUFFIXES
IF(LibSolv_USE_STATIC_LIBS)
    SET( _ORIG_CMAKE_FIND_LIBRARY_SUFFIXES ${CMAKE_FIND_LIBRARY_SUFFIXES})
    SET(CMAKE_FIND_LIBRARY_SUFFIXES .a )
ENDIF()

# Look for the header files
UNSET(LibSolv_INCLUDE_DIRS CACHE)
FIND_PATH(LibSolv_INCLUDE_DIRS NAMES solv/solvable.h)

# Look for the core library
UNSET(LIBSOLV_LIBRARY CACHE)
FIND_LIBRARY(LIBSOLV_LIBRARY NAMES solv)
FIND_PACKAGE_HANDLE_STANDARD_ARGS(LibSolv DEFAULT_MSG LIBSOLV_LIBRARY LibSolv_INCLUDE_DIRS)
MARK_AS_ADVANCED(
    LIBSOLV_FOUND
    LIBSOLV_LIBRARY
)

# Prepare return values and collectiong more components
SET(LibSolv_FOUND ${LIBSOLV_FOUND})
SET(LibSolv_LIBRARIES ${LIBSOLV_LIBRARY})
MARK_AS_ADVANCED(
    LibSolv_FOUND
    LibSolv_LIBRARIES
    LibSolv_INCLUDE_DIRS
)

# Look for components
FOREACH(COMPONENT ${LibSolv_FIND_COMPONENTS})
    STRING(TOUPPER ${COMPONENT} _UPPERCOMPONENT)
    UNSET(LIBSOLV_${_UPPERCOMPONENT}_LIBRARY CACHE)
    FIND_LIBRARY(LIBSOLV_${_UPPERCOMPONENT}_LIBRARY NAMES solv${COMPONENT})
    SET(LibSolv_${COMPONENT}_FIND_REQUIRED ${LibSolv_FIND_REQUIRED})
    SET(LibSolv_${COMPONENT}_FIND_QUIETLY ${LibSolv_FIND_QUIETLY})
    FIND_PACKAGE_HANDLE_STANDARD_ARGS(LibSolv_${COMPONENT} DEFAULT_MSG LIBSOLV_${_UPPERCOMPONENT}_LIBRARY)
    MARK_AS_ADVANCED(
	LIBSOLV_${_UPPERCOMPONENT}_FOUND
	LIBSOLV_${_UPPERCOMPONENT}_LIBRARY
    )
    IF(LIBSOLV_${_UPPERCOMPONENT}_FOUND)
	SET(LibSolv_LIBRARIES ${LibSolv_LIBRARIES} ${LIBSOLV_${_UPPERCOMPONENT}_LIBRARY})
    ELSE()
	SET(LibSolv_FOUND FALSE)
    ENDIF()
ENDFOREACH()

# restore CMAKE_FIND_LIBRARY_SUFFIXES
IF(Solv_USE_STATIC_LIBS)
    SET(CMAKE_FIND_LIBRARY_SUFFIXES ${_ORIG_CMAKE_FIND_LIBRARY_SUFFIXES} )
ENDIF()

IF(LibSolv_FOUND AND NOT LibSolv_FIND_QUIETLY)
    MESSAGE(STATUS "Found LibSolv: ${LibSolv_INCLUDE_DIRS} ${LibSolv_LIBRARIES}")
ENDIF()
