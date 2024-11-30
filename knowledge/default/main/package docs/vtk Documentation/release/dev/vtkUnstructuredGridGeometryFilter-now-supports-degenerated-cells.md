##  vtkUnstructuredGridGeometryFilter now supports degenerate cells

Degenerate cells are cells for which one edge or face is collapsed. It means that a single cell contains duplicated ids. vtkUnstructuredGridGeometryFilter was not correctly handling this configuration, but this is now fixed.
