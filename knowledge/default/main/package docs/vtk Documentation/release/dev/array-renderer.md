## New renderer for shader prototyping

The vtkArrayRenderer class is a new OpenGL mapper focused on prototyping
shader code using vtkDataArray objects bound to texture buffers.
It uses a technique called "vertex pulling," which renders OpenGL primitives
such as points, lines, and triangles with no initial coordinates (i.e., with
an empty vertex array object (VAO)). Instead, the vertex shader is expected
to look up (via a texture sampler) or compute a value that it assigns to the
`gl_Position` output.

To use the class, you simply pass in strings for vertex and fragment shaders,
then bind VTK arrays to texture samplers named in your shader code.

Because vtkArrayRenderer is available in Python, it is easy to edit shader
source code using Python and re-run quickly (with no C++ compilation required).
This class is included in the `RenderingCellGrid` module along with a
test (`TestArrayRenderer.py`) you can modify. Although the example expects
the input data to be a `vtkCellGrid`, this is not a requirement.

This class also makes use of the `vtkGLSLModifier` classes in the
`RenderingCellGrid` module. These classes perform substitutions on your
shader source code to handle some of the tedium of rendering (such as
setting up the camera transform matrices, light position uniforms, and so
on). They also allow you to adjust shader source code while your test script
is running simply by setting up a "live" directory holding a JSON description
of search+replace settings. See the `Rendering/CellGrid/LiveGLSLDebugSample`
directory for an example.
