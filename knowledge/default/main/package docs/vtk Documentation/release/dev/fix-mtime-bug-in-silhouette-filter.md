Fix an MTime bug in vtkPolyDataSilhouette

The output mesh produced by `vtkPolyDataSilhouette` now has a correct MTime when the
line segments in the mesh have changed since the previous execution of this filter.
