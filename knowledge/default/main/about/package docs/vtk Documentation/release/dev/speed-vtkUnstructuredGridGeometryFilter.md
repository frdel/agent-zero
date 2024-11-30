## Improve speed of vtkUnstructuredGridGeometryFilter for higher order cells

In vtkUnstructuredGridGeometryFilter::RequestData, we iterate over all the cells and grab their point ids.
For most of the cells, the almost non-op function GetFaceArray is called.
However, for higher order cells, the face point ids are not constant because they depend on the cell order.

Previously, a generic cell was created (including setting point positions, rational weights, allocating memory for linear approximations, allocating memory for boundaries, etc) in order to obtain these IDs. Then, for each face of a 3-d cell, the point positions, point IDs, and rational weights were set.

We now avoid this memory and time-consuming work with a static function that directly obtains face IDs without creating a generic cell.
