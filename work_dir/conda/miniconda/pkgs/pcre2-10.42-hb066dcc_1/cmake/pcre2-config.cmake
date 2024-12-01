# pcre2-config.cmake
# ----------------
#
# Finds the PCRE2 library, specify the starting search path in PCRE2_ROOT.
#
# Static vs. shared
# -----------------
# To make use of the static library instead of the shared one, one needs
# to set the variable PCRE2_USE_STATIC_LIBS to ON before calling find_package.
# Example:
#   set(PCRE2_USE_STATIC_LIBS ON)
#   find_package(PCRE2 CONFIG COMPONENTS 8BIT)
#
# This will define the following variables:
#
#   PCRE2_FOUND   - True if the system has the PCRE2 library.
#   PCRE2_VERSION - The version of the PCRE2 library which was found.
#
# and the following imported targets:
#
#   PCRE2::8BIT  - The 8 bit PCRE2 library.
#   PCRE2::16BIT - The 16 bit PCRE2 library.
#   PCRE2::32BIT - The 32 bit PCRE2 library.
#   PCRE2::POSIX - The POSIX PCRE2 library.

set(PCRE2_NON_STANDARD_LIB_PREFIX )
set(PCRE2_NON_STANDARD_LIB_SUFFIX )
set(PCRE2_8BIT_NAME pcre2-8)
set(PCRE2_16BIT_NAME pcre2-16)
set(PCRE2_32BIT_NAME pcre2-32)
set(PCRE2_POSIX_NAME pcre2-posix)
find_path(PCRE2_INCLUDE_DIR NAMES pcre2.h DOC "PCRE2 include directory")
if (PCRE2_USE_STATIC_LIBS)
  if (MSVC)
    set(PCRE2_8BIT_NAME pcre2-8-static)
    set(PCRE2_16BIT_NAME pcre2-16-static)
    set(PCRE2_32BIT_NAME pcre2-32-static)
    set(PCRE2_POSIX_NAME pcre2-posix-static)
  endif ()

  set(PCRE2_PREFIX ${CMAKE_STATIC_LIBRARY_PREFIX})
  set(PCRE2_SUFFIX ${CMAKE_STATIC_LIBRARY_SUFFIX})
else ()
  set(PCRE2_PREFIX ${CMAKE_SHARED_LIBRARY_PREFIX})
  if (MINGW AND PCRE2_NON_STANDARD_LIB_PREFIX)
    set(PCRE2_PREFIX "")
  endif ()

  set(PCRE2_SUFFIX ${CMAKE_SHARED_LIBRARY_SUFFIX})
  if (MINGW AND PCRE2_NON_STANDARD_LIB_SUFFIX)
    set(PCRE2_SUFFIX "-0.dll")
  endif ()
endif ()
find_library(PCRE2_8BIT_LIBRARY NAMES ${PCRE2_PREFIX}${PCRE2_8BIT_NAME}${PCRE2_SUFFIX} ${PCRE2_PREFIX}${PCRE2_8BIT_NAME}d${PCRE2_SUFFIX} DOC "8 bit PCRE2 library")
find_library(PCRE2_16BIT_LIBRARY NAMES ${PCRE2_PREFIX}${PCRE2_16BIT_NAME}${PCRE2_SUFFIX} ${PCRE2_PREFIX}${PCRE2_8BIT_NAME}d${PCRE2_SUFFIX} DOC "16 bit PCRE2 library")
find_library(PCRE2_32BIT_LIBRARY NAMES ${PCRE2_PREFIX}${PCRE2_32BIT_NAME}${PCRE2_SUFFIX} ${PCRE2_PREFIX}${PCRE2_8BIT_NAME}d${PCRE2_SUFFIX} DOC "32 bit PCRE2 library")
find_library(PCRE2_POSIX_LIBRARY NAMES ${PCRE2_PREFIX}${PCRE2_POSIX_NAME}${PCRE2_SUFFIX} ${PCRE2_PREFIX}${PCRE2_8BIT_NAME}d${PCRE2_SUFFIX} DOC "8 bit POSIX PCRE2 library")
unset(PCRE2_NON_STANDARD_LIB_PREFIX)
unset(PCRE2_NON_STANDARD_LIB_SUFFIX)
unset(PCRE2_8BIT_NAME)
unset(PCRE2_16BIT_NAME)
unset(PCRE2_32BIT_NAME)
unset(PCRE2_POSIX_NAME)

# Set version
if (PCRE2_INCLUDE_DIR)
  set(PCRE2_VERSION "10.42.0")
endif ()

# Which components have been found.
if (PCRE2_8BIT_LIBRARY)
  set(PCRE2_8BIT_FOUND TRUE)
endif ()
if (PCRE2_16BIT_LIBRARY)
  set(PCRE2_16BIT_FOUND TRUE)
endif ()
if (PCRE2_32BIT_LIBRARY)
  set(PCRE2_32BIT_FOUND TRUE)
endif ()
if (PCRE2_POSIX_LIBRARY)
  set(PCRE2_POSIX_FOUND TRUE)
endif ()

# Check if at least one component has been specified.
list(LENGTH PCRE2_FIND_COMPONENTS PCRE2_NCOMPONENTS)
if (PCRE2_NCOMPONENTS LESS 1)
  message(FATAL_ERROR "No components have been specified. This is not allowed. Please, specify at least one component.")
endif ()
unset(PCRE2_NCOMPONENTS)

# When POSIX component has been specified make sure that also 8BIT component is specified.
set(PCRE2_8BIT_COMPONENT FALSE)
set(PCRE2_POSIX_COMPONENT FALSE)
foreach(component ${PCRE2_FIND_COMPONENTS})
  if (component STREQUAL "8BIT")
    set(PCRE2_8BIT_COMPONENT TRUE)
  elseif (component STREQUAL "POSIX")
    set(PCRE2_POSIX_COMPONENT TRUE)
  endif ()
endforeach()

if (PCRE2_POSIX_COMPONENT AND NOT PCRE2_8BIT_COMPONENT)
  message(FATAL_ERROR "The component POSIX is specified while the 8BIT one is not. This is not allowed. Please, also specify the 8BIT component.")
endif()
unset(PCRE2_8BIT_COMPONENT)
unset(PCRE2_POSIX_COMPONENT)

include(FindPackageHandleStandardArgs)
set(${CMAKE_FIND_PACKAGE_NAME}_CONFIG "${CMAKE_CURRENT_LIST_FILE}")
find_package_handle_standard_args(PCRE2
  FOUND_VAR PCRE2_FOUND
  REQUIRED_VARS PCRE2_INCLUDE_DIR
  HANDLE_COMPONENTS
  VERSION_VAR PCRE2_VERSION
  CONFIG_MODE
)

set(PCRE2_LIBRARIES)
if (PCRE2_FOUND)
  foreach(component ${PCRE2_FIND_COMPONENTS})
    if (PCRE2_USE_STATIC_LIBS)
      add_library(PCRE2::${component} STATIC IMPORTED)
      target_compile_definitions(PCRE2::${component} INTERFACE PCRE2_STATIC)
    else ()
      add_library(PCRE2::${component} SHARED IMPORTED)
    endif ()
    set_target_properties(PCRE2::${component} PROPERTIES
      IMPORTED_LOCATION "${PCRE2_${component}_LIBRARY}"
      INTERFACE_INCLUDE_DIRECTORIES "${PCRE2_INCLUDE_DIR}"
    )
    if (component STREQUAL "POSIX")
      set_target_properties(PCRE2::${component} PROPERTIES
        INTERFACE_LINK_LIBRARIES "PCRE2::8BIT"
        LINK_LIBRARIES "PCRE2::8BIT"
      )
    endif ()

    set(PCRE2_LIBRARIES ${PCRE2_LIBRARIES} ${PCRE2_${component}_LIBRARY})
    mark_as_advanced(PCRE2_${component}_LIBRARY)
  endforeach()
endif ()

mark_as_advanced(
  PCRE2_INCLUDE_DIR
)
