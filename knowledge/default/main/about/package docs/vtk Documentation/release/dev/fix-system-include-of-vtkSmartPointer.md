## fix system include of vtkSmartPointer

Fixed system include of `vtkSmartPointer.h` within `vtkXMLUnstructuredDataWriter.h`
that prevented it from being used within a project built using Bazel.
