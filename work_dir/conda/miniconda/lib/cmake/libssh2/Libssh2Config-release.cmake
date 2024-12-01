#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "Libssh2::libssh2_shared" for configuration "Release"
set_property(TARGET Libssh2::libssh2_shared APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(Libssh2::libssh2_shared PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/libssh2.1.0.1.dylib"
  IMPORTED_SONAME_RELEASE "@rpath/libssh2.1.dylib"
  )

list(APPEND _cmake_import_check_targets Libssh2::libssh2_shared )
list(APPEND _cmake_import_check_files_for_Libssh2::libssh2_shared "${_IMPORT_PREFIX}/lib/libssh2.1.0.1.dylib" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
