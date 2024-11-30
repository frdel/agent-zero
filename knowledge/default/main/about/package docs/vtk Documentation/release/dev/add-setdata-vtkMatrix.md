# Add new method to set elements for vtkMatrix3x3 and vtkMatrix4x4

You can now call `vtkMatrix3x3::SetData(const double[9])` or `vtkMatrix4x4::SetData(const double[16])`
to initialize the elements of the matrices from external memory.
