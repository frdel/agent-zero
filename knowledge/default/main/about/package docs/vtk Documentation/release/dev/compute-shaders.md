## Add support for compute shaders

It's now possible to attach a compute shader to a `vtkShaderProgram` using `SetComputeShader`.
The shader can be invoked if an OpenGL context exists by calling `glDispatchCompute` function.
OpenGL >=4.3 or `GL_ARB_compute_shader` extension is required.
