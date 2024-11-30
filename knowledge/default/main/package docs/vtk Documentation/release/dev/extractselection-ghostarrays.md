# Ghost arrays in vtkExtractSelection

A new flag `TestGhostArrays` is added to `vtkExtractSelection` that when enabled, asks the
extraction filter to skip hidden points/cells from passing through to the output.  By default, this
flag is `false` and the default behavior of the class remains the same.
