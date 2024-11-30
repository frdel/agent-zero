## vtkOpenGLRenderWindow allows to blit back the depth buffer too (#19256)

`vtkOpenGLRenderWindow` allowed to blit back the rendered content to the current
(external) framebuffer by setting the attribute `FrameBlitMode` to `BlitToCurrent`.

By setting this attribute to `BlitToCurrentWithDepth`, the depth buffer is also
blitted back, which allows to do further rendering outside of VTK with correct
occlusion of the VTK parts.
