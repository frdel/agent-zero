## Introduce vtkDataObjectMeshCache

vtkDataObjectMeshCache is a new class to store and reuse the mesh of a vtkDataSet,
and composite of vtkDataSet.
It allows to copy attributes from an updated input if original ids are known.

The VTK pipeline mechanism is useful to link filters one after the
other, and automatically trigger computation when the inputs change.
But sometime you may feel like some of the computation could be shortened.

For instance, a filter, "Consumer", creates a new mesh and
forward the data arrays from its input to the output during the processing.
On a new execution, Consumer may know that its output will have
the same mesh, mainly because the input mesh was not modified, and
neither was Consumer itself. Only the data arrays from the input have
change and should be forwarded to the output.

Instead of implementing such logic itself, Consumer can instead rely on vtkDataObjectMeshCache,
in order to easily reuse the previously computed mesh, and forward the new data arrays.
