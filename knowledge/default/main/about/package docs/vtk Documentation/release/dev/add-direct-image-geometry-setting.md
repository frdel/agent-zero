## API for directly setting IndexToPhysicalMatrix and PhysicalToIndexMatrix in vtkImageData

You can now set image geometry (origin, spacing, axis directions) in a `vtkImageData` object from a 4x4 matrix
by a single method call, using the new `ApplyIndexToPhysicalMatrix` and `ApplyPhysicalToIndexMatrix` methods.
