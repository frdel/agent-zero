#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "libmamba" for configuration "Release"
set_property(TARGET libmamba APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(libmamba PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/libmamba.2.0.0.dylib"
  IMPORTED_SONAME_RELEASE "@rpath/libmamba.2.dylib"
  )

list(APPEND _cmake_import_check_targets libmamba )
list(APPEND _cmake_import_check_files_for_libmamba "${_IMPORT_PREFIX}/lib/libmamba.2.0.0.dylib" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
