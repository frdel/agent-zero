## add-egl-wheels

VTK now provides wheels using EGL for rendering. They are available on VTK's
website and [the package registry on GitLab][vtk-package-registry] and not PyPI
since they require a user-provided `libEGL.so.1` at runtime.

[vtk-package-registry]: https://gitlab.kitware.com/vtk/vtk/-/packages
