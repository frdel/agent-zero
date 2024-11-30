# Support OpenGL tessellation shaders

VTK now supports tessellation control and tessellation evaluation shaders in an OpenGL
shader program. You can use the new enums `vtkShader::TessControl` and `vtkShader::TessEvaluation`
to create shaders of type `GL_TESS_CONTROL_SHADER` and `GL_TESS_EVALUATION_SHADER` respectively.

The new overload of `vtkShaderProgram::ReadyShaderProgram` accepts source codes
for tessellation control and evaluation shaders.

This feature is available starting from OpenGL version 4.1. You can use `vtkShader::IsTessellationShaderSupported()` to confirm whether the OpenGL driver supports tessellation shaders. For OpenGL 4.0 and lower, VTK automatically enables the
`GL_ARB_tessellation_shader` extension while populating `//VTK::System::Dec` in shader code.
