# Remove OpenGL module

VTK no longer provides the `VTK::opengl` module because VTK now loads an OpenGL library
at runtime using `glad`.

The CMake setting `OpenGL_GL_PREFERENCE` is no longer relevant because VTK does not look for
OpenGL at compile time. On Linux distributions, the `glad` OpenGL loader always loads `libGL.so` at runtime.
