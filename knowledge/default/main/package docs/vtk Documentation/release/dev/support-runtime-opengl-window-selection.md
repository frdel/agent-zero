# Add support for fallback to EGL or OSMesa in Linux and Windows at runtime

On Linux, VTK will now automatically fallback to `EGL` when there is no X display present or it is not capable of OpenGL.
In case the system is not configured for `EGL`, VTK will fallback to OSMesa. The reason for fallback will be printed to console.

Similarly on Windows, VTK will now automatically fallback to OSMesa if the OpenGL drivers on Windows system are too old i,e do not
support OpenGL 3.2 or higher.

You can learn about the new behavior of the OpenGL build settings in [](https://docs.vtk.org/en/latest/build_instructions/build_settings.html#opengl-related-build-options)

To enable runtime selection, VTK now integrates the modern OpenGL loader library [glad](https://github.com/Dav1dde/glad) as a [third-party project](/developers_guide/git/thirdparty-projects.md), replacing `glew`, which did not support compiling both `GLX` and `EGL` in the same build

If OSMesa is not installed, VTK prints a warning to the console and suggests installing OSMesa.

You can enforce a specific render window by setting the `VTK_DEFAULT_OPENGL_WINDOW` environment variable. See [](https://docs.vtk.org/en/latest/advanced/runtime_settings.html#opengl).
