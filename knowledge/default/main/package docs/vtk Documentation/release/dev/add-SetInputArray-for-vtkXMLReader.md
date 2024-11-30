# Add SetInputArray(vtkCharArray*) method for vtkXMLReader

You can now pass `vtkCharArray` to vtkXMLReader and subclasses using
the new `SetInputArray()` method. This reduces an extra copy made
to the input string.
