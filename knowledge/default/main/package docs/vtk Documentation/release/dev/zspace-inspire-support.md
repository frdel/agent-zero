## zSpace Inspire Support

Add support to new zSpace Inspire hardware in VTK.

We added new `vtkZSpaceWin32RenderWindow` and `vtkZSpaceGenericRenderWindow` classes in order to support
the specific rendering mode of the latest zSpace hardware. The zSpace Inspire do not rely on quad-buffering
to display stereo content like previous models. It uses it's dedicated stereo display instead to perform
stereo rendering. Note that the zSpace Stereo Core Compatibility API should be used in that case.
