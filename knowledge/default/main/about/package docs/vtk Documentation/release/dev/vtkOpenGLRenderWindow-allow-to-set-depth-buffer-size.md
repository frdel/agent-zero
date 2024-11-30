## vtkOpenGLRenderWindow allows to set depth buffer bit size of render buffers (#19255)

The bit size of depth buffers can be set for `vtkOpenGLRenderWindow` through the
attribute `RenderBufferTargetDepthSize` (this needs to be set before the render
buffers are created).

This can be useful when working with `vtkExternalOpenGLRenderWindow` and the
bit size of the external depth buffer can't be set to 32.
