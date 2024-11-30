## Rework the vktHyperTreeGridGeometryFilter

The vtkHyperTreeGridGeometryFilter now delegates the work to dedicated implementation classes,
depending on the dimension of the HTG (see `vtkvtkHyperTreeGridGeometry3DImpl` for example).

Furthermore, the geometry filter now supports interfaces in the 1D, 2D and 3D cases.
