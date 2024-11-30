## Caption Representation fitting

The vtkCaptionRepresentation can now be sized using a configurable API `SetFit`. The two options
available to the user are `VTK_FIT_TO_BORDER` and `VTK_FIT_TO_TEXT`. When fitting to border, the
text is sized to fit in the border, thus allowing to resize the text with the viewport. When fit to
text is enabled, the text always remains the specified font size.
