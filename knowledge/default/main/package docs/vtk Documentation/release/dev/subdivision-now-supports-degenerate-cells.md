## Revisit subdivision of nonlinear cells in vtkDataSetSurfaceFilter

In a recent change, the cell->triangulate function has been updated to return local point ids instead of global ids.
Today, we take advantage of this to use local ids in the nonlinear subdivision algorithms as well.

The main motivation of this change is that working with local ids helps supporting nonlinear subdivisions of degenerate cells.
Indeed, the subdivision algorithm is now applied in the parametric space ( that is not degenerated), instead of the physical space.
Once all the subdivisions are done, we move back to the physical space.
