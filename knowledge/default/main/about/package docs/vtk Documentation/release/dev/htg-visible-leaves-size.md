## Hyper Tree Grid Compute Visible Leaves Size filter

A new HTG utility filter for HTG has been added : `vtkHyperTreeGridVisibleLeavesSize`.
This filter creates 2 new cell fields using implicit arrays under the hood:
- `ValidCell` has a (double) value of 1.0 for visible (non ghost, non masked) leaf cells, and 0.0 for the others.
- `CellSize`'s value corresponds to the volume of the cell in 3D, or area in 2D.

`ValidCell` can allow, with `CellSize`, to compute volume aggregations over the HTG.
