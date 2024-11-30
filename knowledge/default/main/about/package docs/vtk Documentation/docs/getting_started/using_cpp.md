# Using C++ and CMake

CMake is an open-source platform-independent build system that manages the
entire software build process, from source code to executable binary. If you're
new to CMake, you can find more information on the [CMake website](https://cmake.org).

**Installing a binary release**

Pre-built VTK releases maintained by the community exist for a number of
distributions, as shown in the following table:


| Operating System/ Package manager  | Package Name    | Version |
|------------------------------------|-----------------|---------|
| Fedora Rawhide                     |  vtk-devel      | ![Fedora rawhide package](https://img.shields.io/fedora/v/vtk-devel) |
| Fedora 38                          |  vtk-devel      | ![Fedora 38 package](https://img.shields.io/fedora/v/vtk-devel/f38) |
| Fedora 37                          |  vtk-devel      | ![Fedora 37 package](https://img.shields.io/fedora/v/vtk-devel/f37) |
| Ubuntu 23.04 (lunar)               |  libvtk9-dev    | ![Ubuntu lunar package](https://img.shields.io/ubuntu/v/vtk9/lunar)
| Ubuntu 22.10 (kinetic)             |  libvtk9-dev    | ![Ubuntu kinetic package](https://img.shields.io/ubuntu/v/vtk9/kinetic)
| Ubuntu 22.04 (jammy)               |  libvtk9-dev    | ![Ubuntu jammy package](https://img.shields.io/ubuntu/v/vtk9/jammy)
| Ubuntu 20.04 (focal)               |  libvtk7-dev    | ![Ubuntu focal package](https://img.shields.io/ubuntu/v/vtk7/focal)
| Debian unstable                    |  libvtk9-devel  | ![Debian unstable package](https://img.shields.io/debian/v/libvtk9-dev) |
| Debian testing                     |  libvtk9-devel  | ![Debian testing package](https://img.shields.io/debian/v/libvtk9-dev/testing) |
| Debian stable                      |  libvtk9-devel  | ![Debian stable package](https://img.shields.io/debian/v/libvtk9-dev/stable) |
| Gentoo                             |     vtk         | 	[![Gentoo package](https://repology.org/badge/version-for-repo/gentoo/vtk.svg)](https://repology.org/project/vtk/versions)
| homebrew                           |     vtk         | ![homebrew version](https://img.shields.io/homebrew/v/vtk)|
| vckpg                              |     vtk         | ![Vcpkg](https://img.shields.io/vcpkg/v/vtk) |
| spack                              |     vtk         | ![Spack](https://img.shields.io/spack/v/vtk) |


Note that these packages may be lacking some optional features such as mpi, qt
etc. or, they may not contain the latest VTK features.  Check the documentation
of each package to verify that the build contains what you need.  If what you
need is missing you will need to [build vtk from scratch](../build_instructions/index.md).

**Building an executable**

Once VTK is installed using either of the methods above you can use it in your
project utilizing the
[find_package](https://cmake.org/cmake/help/latest/command/find_package.html)
infrastructure of cmake:

```cmake
find_package(VTK
  COMPONENTS
  .. list of vtk modules to link to
)

# your executable
add_executable(testExample ...)

# link to required VTK libraries
target_link_libraries(testExample
  PRIVATE
   ${VTK_LIBRARIES}
)

vtk_module_autoinit(
  TARGETS testExample
  MODULES ${VTK_LIBRARIES}
)
```

{cmake:command}`vtk_module_autoinit` is responsible for triggering static code construction required for some VTK classes.
For more details regarding the autoinit system of VTK see [here](../api/cmake/ModuleSystem.md#autoinit).

The list of required vtk modules depends on the files `#include`d in your code. The module a header file belongs to is determined
in most cases by its location in the VTK source tree. For, example `vtkXMLPolyDataReader` is located under `IO/XML` so it belongs to the `IOXML` module,
to verify check the accompanying [`vtk.module`](https://gitlab.kitware.com/vtk/vtk/-/blob/master/IO/XML/vtk.module) file in the same directory.

The above method works in most cases but it does not express the dependencies that some module have. A better (and easier) way to
find the required modules is the [VTKModulesForCxx](https://examples.vtk.org/site/Python/Utilities/VTKModulesForCxx) script.

For example, running the script on the [CylinderExample](https://examples.vtk.org/site/Cxx/GeometricObjects/CylinderExample)
we get the following suggestion:

```cmake
find_package(VTK
 COMPONENTS
    CommonColor
    CommonCore
    FiltersSources
    RenderingCore
    #
    # These modules are suggested since they implement an existing module.
    # You may need to uncomment one or more of these.
    # If vtkRenderWindow is used and you want to use OpenGL,
    #   you also need the RenderingOpenGL2 module.
    # If vtkRenderWindowInteractor is used,
    #    uncomment RenderingUI and possibly InteractionStyle.
    # If text rendering is used, uncomment RenderingFreeType
    #
    # InteractionStyle  # implements VTK::RenderingCore
    # RenderingCellGrid # implements VTK::RenderingCore
    # RenderingFreeType # implements VTK::RenderingCore
    # RenderingOpenGL2  # implements VTK::RenderingCore
    # RenderingUI       # implements VTK::RenderingCore
)
```

Based on the suggestions of the script and the template above the relevant sections of the `CMakeLists.txt` are:

```cmake
...
find_package(VTK COMPONENTS
  CommonColor
  CommonCore
  FiltersSources
  InteractionStyle
  RenderingContextOpenGL2
  RenderingCore
  RenderingFreeType
  RenderingGL2PSOpenGL2
  RenderingOpenGL2
)

add_executable(CylinderExample CylinderExample.cxx)
target_link_libraries(CylinderExample PRIVATE ${VTK_LIBRARIES})
# vtk_module_autoinit is needed
vtk_module_autoinit(
  TARGETS CylinderExample
  MODULES ${VTK_LIBRARIES}
)
```

The full source of the example can be found [here](https://examples.vtk.org/site/Cxx/GeometricObjects/CylinderExample/).

To build the example:

```
mkdir build
cd build
ccmake ../ # or cmake-gui if on Windows
```
Hit `C` if using `ccmake` or the configure button if using `cmake-gui`.
If VTK was built from scratch you will need to set `VTK_DIR` to the installation path.
If `ccmake`/`cmake-gui` reports no errors quit `ccmake`/`cmake-gui` and build the project as follows:

```
cmake --build .
```
To run the example

```
./CylinderExample
```

For more examples check the
[tutorials](https://kitware.github.io/vtk-examples/site/Cxx/#tutorial),
[how to guides](https://kitware.github.io/vtk-examples/site/CxxHowTo) or
[examples](https://kitware.github.io/vtk-examples/site/Cxx) sections of the vtk examples website.
