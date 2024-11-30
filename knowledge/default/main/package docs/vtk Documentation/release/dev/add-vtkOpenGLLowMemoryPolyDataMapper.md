# New OpenGL polydata mapper for devices and environments with low memory

The new `vtkOpenGLLowMemoryPolyDataMapper` is the default factory override
for `vtkPolyDataMapper` when `VTK_OPENGL_USE_GLES=ON`. This mapper is helpful because:

1. `vtkOpenGLPolyDataMapper` uses geometry shaders which are unavailable in GLES 3.0.
2. The `vtkOpenGLES30PolyDataMapper` consumes 10x more memory than the mesh size.

This mapper uses [vertex-pulling](https://webglfundamentals.org/webgl/lessons/webgl-pulling-vertices.html)
in the vertex shader to draw primitives and fragment shading to evaluate normals and colors.
