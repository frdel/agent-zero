# Building Python Wheels

```{tip}
For complete build instructions see [here](../build_instructions/build.md).
```

VTK also supports creating a Python wheel containing its Python wrappers for
Python3. This is supported by setting the `VTK_WHEEL_BUILD` flag. This changes
the build directory structure around to match that expected by wheels. Once
configured, the build tree may be built as it would be normally and then the
generated `setup.py` file used to create the wheel. Note that the `bdist_wheel`
command requires that the `wheel` package is available (`pip install wheel`).

```sh
cmake -GNinja -DVTK_WHEEL_BUILD=ON -DVTK_WRAP_PYTHON=ON path/to/vtk/source
ninja
python3 setup.py bdist_wheel
```

Any modules may be turned on or off as in a normal VTK build. Certain modules
add features to the generated wheel to indicate their availability. These flags
are not meant to be comprehensive, but any reasonable feature flags may be
added to `CMake/vtkWheelFinalization.cmake` as needed.

Note that the wheel will not include any external third party libraries in its
wheel (e.g., X11, OpenGL, etc.) to avoid conflicts with systems or other wheels
doing the same.

## Modifying Version and/or Distribution Name

When generating a wheel, you can modify the distribution name and/or add a
suffix to the wheel version string.

By default, the distribution name is `vtk` though you can add a suffix via the
`VTK_DIST_NAME_SUFFIX` CMake variable (e.g., set `VTK_DIST_NAME_SUFFIX`).
An underscore (`_`) character is automatically placed between `vtk` and the value
of `VTK_DIST_NAME_SUFFIX`. Please use `_` characters for further delimination in
the suffix value. Example setting:

```cmake
set(VTK_DIST_NAME_SUFFIX "foo" CACHE STRING "")
```

By default (outside of a CI release build), `dev0` is appended to the version of
the package (e.g., `9.2.2.dev0`). This suffix can be controlled through the
`VTK_VERSION_SUFFIX` CMake variable and is useful if generating multiple
wheels and wanting to differentiate the build variants by the version string of
the package.

```cmake
set(VTK_VERSION_SUFFIX "dev0" CACHE STRING "")
```
