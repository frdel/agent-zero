### MotivationsThe vtkCell:
Triangulate function returns both the point ids and point coordinates of the cells. But most of the time, when this is called, only the ids are used.

Avoiding to return point coordinates would remove some unnecessary allocations and point copies.
But the most important gains are for Bezier cells where nodes are not interpolatory, and so returning the points involve multiple basis evaluations.
Thanks to that, vtkDataSetSurfaceFilter is much faster with Bezier cells, and we can see the effects when rendering in Paraview.

### Implementations
Now, in the vtkCell interfaces, there are three functions:
* Triangulate( ids, points ): Existing function that returns the triangulated points and global ids (function not deprecated)
* TriangulateIds( ids ): New function that only returns the triangulated global ids
* TriangulateLocalIds( ids ): New function that only returns the triangulated local ids.
Before, Triangulate was implemented for each cell type. Now Triangulate is only implemented in the source code of vtkCell, and it is TriangulateLocalIds that is implemented for each cell type.
Triangulate and TriangulateIds are both called TriangulateLocalIds in the source code of vtkCell.


### Minor additional changes:
* Fix a bug in vtkQuadraticPolygon::PermuteFromPolygon
* Slightly speed up vtkDataSetSurfaceFilter for nonlinear cells.
* Slightly speed up vtkPolygon::BoundedTriangulate
* Remove a lot of DeepCopy in vtkPolygon
* Deprecate vtkPolygon::Triangulate and vtkQuadraticPolygon::Triangulate function.
