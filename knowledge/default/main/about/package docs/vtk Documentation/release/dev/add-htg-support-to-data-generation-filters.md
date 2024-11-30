## Add HTG support to data generation filters

It's now possible to generate random attributes, cell IDs, process IDs and global IDs for `vtkHyperTreeGrid` in VTK.

- The `vtkRandomAttribute` generator now supports HTGs as input.
- The `vtkGenerateIds` filter replaces the `vtkIdFilter` and now support `vtkHyperTreeGrid` in addition to `vtkDataSet`. The `vtkIdFilter` is now deprecated.
- The dedicated `vtkHyperTreeGridGenerateProcessIds` filter has been added to generate process IDs.
- The dedicated `vtkHyperTreeGridGenerateGlobalIds` filter has been added to generate global IDs.
