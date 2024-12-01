############################################################################
# Copyright (c) 2019, QuantStack and Mamba Contributors                    #
#                                                                          #
# Distributed under the terms of the BSD 3-Clause License.                 #
#                                                                          #
# The full license is in the file LICENSE, distributed with this software. #
############################################################################

# libmamba cmake module
# This module sets the following variables in your project::
#
#   libmamba_FOUND - true if libmamba found on the system
#   libmamba_INCLUDE_DIRS - the directory containing libmamba headers
#   libmamba_LIBRARY - the library for dynamic linking
#   libmamba_STATIC_LIBRARY - the library for static linking
#   libmamba_FULL_STATIC_LIBRARY - the library for static linking, incl. static deps


####### Expanded from @PACKAGE_INIT@ by configure_package_config_file() #######
####### Any changes to this file will be overwritten by the next CMake run ####
####### The input file was libmambaConfig.cmake.in                            ########

get_filename_component(PACKAGE_PREFIX_DIR "${CMAKE_CURRENT_LIST_DIR}/../../../" ABSOLUTE)

macro(set_and_check _var _file)
  set(${_var} "${_file}")
  if(NOT EXISTS "${_file}")
    message(FATAL_ERROR "File or directory ${_file} referenced by variable ${_var} does not exist !")
  endif()
endmacro()

macro(check_required_components _NAME)
  foreach(comp ${${_NAME}_FIND_COMPONENTS})
    if(NOT ${_NAME}_${comp}_FOUND)
      if(${_NAME}_FIND_REQUIRED_${comp})
        set(${_NAME}_FOUND FALSE)
      endif()
    endif()
  endforeach()
endmacro()

####################################################################################

set(CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR};${CMAKE_MODULE_PATH}")



include(CMakeFindDependencyMacro)
find_dependency(fmt)
find_dependency(nlohmann_json)
find_dependency(spdlog)
find_dependency(Threads)
find_dependency(tl-expected)
find_dependency(zstd)
find_dependency(BZip2)
find_dependency(yaml-cpp)

if(NOT (TARGET libmamba OR TARGET libmamba-static))
    include("${CMAKE_CURRENT_LIST_DIR}/libmambaTargets.cmake")

    if (TARGET libmamba-static)
        get_target_property(libmamba_INCLUDE_DIR libmamba-static INTERFACE_INCLUDE_DIRECTORIES)
        get_target_property(libmamba_STATIC_LIBRARY libmamba-static LOCATION)
    endif ()

    if (TARGET libmamba)
        get_target_property(libmamba_INCLUDE_DIR libmamba INTERFACE_INCLUDE_DIRECTORIES)
        get_target_property(libmamba_LIBRARY libmamba LOCATION)
    endif ()
endif()
