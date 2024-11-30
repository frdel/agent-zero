# Hardware selection for vtkCellGridMapper

You can now pick actors that represent a `vtkCellGrid` using hardware selectors.
The `vtkCellGridMapper` allows you to pick cells but not points (because the cell-grid data model does not require cells to be defined by points).
The resulting selection nodes for cell-grids provide additional properties that specify the type of cell selected.
