# Module Migration from VTK 8.2 to 9+

VTK 8.2 and older contained a module system which was based on variables and
informed CMake's migration to target-based properties and interactions. This
was incompatible with the way VTK ended up doing it. With VTK 9, its module
system has been reworked to use CMake's targets.

This document may be used as a guide to updating code using old VTK modules into
code using new VTK modules.

## Using modules

If your project is just using VTK's modules and not declaring any of your own
modules, porting involves a few changes to the way VTK is found and used.

The old module system made variables available for using VTK.

```cmake
find_package(VTK
  REQUIRED
  COMPONENTS
    vtkCommonCore
    vtkRenderingOpenGL2)
include(${VTK_USE_FILE})

add_library(usesvtk ...)
target_link_libraries(usesvtk ${visibility} ${VTK_LIBRARIES})
target_include_directories(usesvtk ${visibility} ${VTK_INCLUDE_DIRS})

# Pass any VTK autoinit defines to the target.
target_compile_definitions(usesvtk PRIVATE ${VTK_DEFINITIONS})
```

This causes problems if VTK is found multiple times within a source tree with
different components. The new pattern is:

```cmake
find_package(VTK
  #9.0 # Compatibility support is not provided if 9.0 is requested.
  REQUIRED
  COMPONENTS
    # Old component names are OK, but deprecated.
    #vtkCommonCore
    #vtkRenderingOpenGL2
    # New names reflect the target names in use.
    CommonCore
    RenderingOpenGL2)
# No longer needed; warns or errors depending on the version requested when
# finding VTK.
#include(${VTK_USE_FILE})

add_library(usesvtk ...)
# VTK_LIBRARIES is provided for compatibility, but not recommended.
#target_link_libraries(usesvtk ${visibility} ${VTK_LIBRARIES})
target_link_libraries(usesvtk ${visibility} VTK::CommonCore VTK::RenderingOpenGL2)

# Rather than defining a single `VTK_DEFINITIONS` for use by all relevant
# targets, the definitions are made as needed with the exact set needed for the
# listed modules.
vtk_module_autoinit(
  TARGETS usesvtk
  #MODULES ${VTK_LIBRARIES} # Again, works, but is not recommended.
  MODULES VTK::CommonCore VTK::RenderingOpenGL2)
```

## Module declaration

The old module system had CMake code declare modules in `module.cmake` files.
This allowed logic and other things to happen within them which could cause
module dependencies to be hard to follow. The new module system now provides
facilities for disabling modules in certain configurations (using `CONDITION`)
and for optionally depending on modules (using `OPTIONAL_DEPENDS`).

```cmake
if (NOT SOME_OPTION)
  set(depends)
  if (SOME_OTHER_OPTION)
    list(APPEND depends vtkSomeDep)
  endif ()
  vtk_module(vtkModuleName
    GROUPS
      # groups the module belongs to
    KIT
      # the kit the module belongs to
    IMPLEMENTS
      # modules containing vtkObjectFactory instances that are implemented here
    DEPENDS
      # public dependencies
      #${depends} # no analogy in the new system
    PRIVATE_DEPENDS
      # private dependencies
      ${depends}
    COMPILE_DEPENDS
      # modules which must be built before this one but which are not actually
      # linked.
    TEST_DEPENDS
      # test dependencies
    TEST_OPTIONAL_DEPENDS
      # optional test dependencies
      ${depends}
    #EXCLUDE_FROM_WRAPPING
      # present for modules which cannot be wrapped
  )
endif ()
```

This is now replaced with a declarative file named `vtk.module`. This file is
not CMake code and is instead parsed as an argument list in CMake (variable
expansions are also not allowed). The above example would translate into:

```
MODULE
  vtkModuleName
CONDITION
  SOME_OPTION
GROUPS
  # groups the module belongs to
KIT
  # the kit the module belongs to
#IMPLEMENTABLE # Implicit in the old build system. Now explicit.
IMPLEMENTS
  # modules containing vtkObjectFactory instances that are implemented here
DEPENDS
  # public dependencies
PRIVATE_DEPENDS
  # private dependencies
OPTIONAL_DEPENDS
  vtkSomeDep
ORDER_DEPENDS
  # modules which must be built before this one but which are not actually
  # linked.
TEST_DEPENDS
  # test dependencies
TEST_OPTIONAL_DEPENDS
  # optional test dependencies
  vtkSomeDep
#EXCLUDE_WRAP
  # present for modules which cannot be wrapped
```

Modules may also now be provided by the current project or by an external
project found by `find_package` as well.

## Declaring sources

Sources used to be listed just as `.cxx` files. The module system would then
search for a corresponding `.h` file, then add it to the list. Some source file
properties could be used to control header-only or private headers.

In this example, we have a module with the following sources:

  - `vtkPublicClass.cxx` and `vtkPublicClass.h`: Public VTK class meant to be
    wrapped and its header installed.
  - `vtkPrivateClass.cxx` and `vtkPrivateClass.h`: Private VTK class not meant
    for use outside of the module.
  - `helper.cpp` and `helper.h`: Private API, but not following VTK's naming
    conventions.
  - `public_helper.cpp` and `public_helper.h`: Public API, but not following
    VTK's naming conventions.
  - `vtkImplSource.cxx`: A source file without a header.
  - `public_header.h`: A public header without a source file.
  - `template.tcc` and `template.h`: Public API, but not following VTK's naming
    conventions.
  - `private_template.tcc` and `private_template.h`: Private API, but not
    following VTK's naming conventions.
  - `vtkPublicTemplate.txx` and `vtkPublicTemplate.h`: Public template sources.
    Wrapped and installed.
  - `vtkPrivateTemplate.txx` and `vtkPrivateTemplate.h`: Private template
    sources.
  - `vtkOptional.cxx` and `vtkOptional.h`: Private API which requires an
    optional dependency.

The old module's way of building these sources is:

```cmake
set(Module_SRCS
  vtkPublicClass.cxx
  vtkPrivateClass.cxx
  helper.cpp
  helper.h
  public_helper.cpp
  public_helper.h
  public_header.h
  vtkImplSource.cxx
  vtkPublicTemplate.txx
  vtkPrivateTemplate.txx
  template.tcc # Not detected as a template, so not installed.
  template.h
  private_template.tcc
  private_template.h
)

# Mark some files as only being header files.
set_source_files_properties(
  public_header.h
  HEADER_FILE_ONLY
)

# Mark some headers as being private.
set_source_files_properties(
  helper.h
  private_template.h
  public_header.h
  template.h
  vtkImplSource.cxx # no header
  vtkPrivateTemplate.h
  PROPERTIES SKIP_HEADER_INSTALL 1
)

set(${vtk-module}_HDRS # Magic variable
  public_helper.h
  template.h
  #helper.h # private headers just go ignored.
)

# Optional dependencies are detected through variables.
if (Module_vtkSomeDep)
  list(APPEND Module_SRCS
    # Some optional file.
    vtkOptional.cxx)
endif ()

vtk_module_library(vtkModuleName ${Module_SRCS})
```

While with the new system, source files are explicitly declared using argument
parsing.

```cmake
set(classes
  vtkPublicClass)
set(private_classes
  vtkPrivateClass)
set(sources
  helper.cpp
  public_helper.cpp
  vtkImplSource.cxx)
set(headers
  public_header.h
  public_helper.h
  template.h)
set(private_headers
  helper.h
  private_template.h)

set(template_classes
  vtkPublicTemplate)
set(private_template_classes
  vtkPrivateTemplate)
set(templates
  template.tcc)
set(private_templates
  private_template.tcc)

# Optional dependencies are detected as targets.
if (TARGET vtkSomeDep)
  # Optional classes may not be public (though there's no way to actually
  # enforce it, optional dependencies are always treated as private.
  list(APPEND private_classes
    vtkOptional)
endif ()

vtk_module_add_module(vtkModuleName
  # File pairs which follow VTK's conventions. The headers will be wrapped and
  # installed.
  CLASSES ${classes}
  # File pairs which follow VTK's conventions, but are not for use outside the
  # module.
  PRIVATE_CLASSES ${private_classes}
  # Standalone sources (those without headers or which do not follow VTK's
  # conventions).
  SOURCES ${sources}
  # Standalone headers (those without sources or which do not follow VTK's
  # conventions). These will be installed.
  HEADERS ${public_headers}
  # Standalone headers (those without sources or which do not follow VTK's
  # conventions), but are not for use outside the module.
  PRIVATE_HEADERS ${private_headers}

  # Templates are also supported.

  # Template file pairs which follow VTK's conventions. Both files will be
  # installed (only the headers will be wrapped).
  TEMPLATE_CLASSES ${template_classes}
  # Template file pairs which follow VTK's conventions, but are not for use
  # outside the module.
  PRIVATE_TEMPLATE_CLASSES ${private_template_classes}
  # Standalone template files (those without headers or which do not follow
  # VTK's conventions). These will be installed.
  TEMPLATES ${templates}
  # Standalone template files (those without headers or which do not follow
  # VTK's conventions), but are not for use outside the module.
  PRIVATE_TEMPLATES ${private_templates}
)
```

Note that the arguments with `CLASSES` in their name expand to pairs of files
with the `.h` and either `.cxx` or `.txx` extension based on whether it is a
template or not. Projects not using this convention may use the `HEADERS`,
`SOURCES`, and `TEMPLATES` arguments instead.

## Object Factories

Previously, object factories were made using implicit variable declaration magic
behind the scenes. This is no longer the case and proper CMake APIs for them are
available.

```cmake
set(sources
  vtkObjectFactoryImpl.cxx
  # This path is made by `vtk_object_factory_configure` later.
  "${CMAKE_CURRENT_BINARY_DIR}/${vtk-module}ObjectFactory.cxx")

# Make a list of base classes we will be overriding.
set(overrides vtkObjectFactoryBase)
# Make a variable declaring what the override for the class is.
set(vtk_module_vtkObjectFactoryBase_override "vtkObjectFactoryImpl")
# Generate a source using the list of base classes overridden.
vtk_object_factory_configure("${overrides}")

vtk_module_library("${vtk-module}" "${sources}")
```

This is now handled using proper APIs instead of variable lookups.

```cmake
set(classes
  vtkObjectFactoryImpl)

# Explicitly declare the override relationship.
vtk_object_factory_declare(
  BASE      vtkObjectFactoryBase
  OVERRIDE  vtkObjectFactoryImpl)
# Collects the set of declared overrides and writes out a source file.
vtk_object_factory_declare(
  # The path to the source is returned as a variable.
  SOURCE_FILE factory_source
  # As is its header file.
  HEADER_FILE factory_header
  # The export macro is now explicitly passed (instead of assumed based on the
  # current module context).
  EXPORT_MACRO MODULE_EXPORT)

vtk_module_add_module(vtkModuleName
  CLASSES ${classes}
  SOURCES "${factory_source}"
  PRIVATE_HEADERS "${factory_header}")
```

## Building a group of modules

This was not well supported in the old module system. Basically, it involved
setting up the source tree like VTK expects and then including the
`vtkModuleTop` file. This is best just rewritten using the following CMake APIs:

  - {cmake:command}`vtk_module_find_modules`
  - {cmake:command}`vtk_module_find_kits`
  - {cmake:command}`vtk_module_scan`
  - {cmake:command}`vtk_module_build`
