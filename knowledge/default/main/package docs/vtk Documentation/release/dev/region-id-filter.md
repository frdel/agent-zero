## vtkGenerateRegionIds

`vtkGenerateRegionIds` is a new polydata filter that adds a CellData array, containing a region identifier.
A region is defined as a collection of cells that match some local criteria. Two cells are on the same region if:
 - they share at least one point
 - the angle between their normals is less than a threshold.

The threshold, `MaxAngle` is configurable.
The resulting array name is configurable and is `vtkRegionIds` by default.

The concept is similar to `vtkConnectivityFilter`, as it defined a region of cells and mark them in a new Array.
The algorithm is similar to the `vtkFeatureEdges` one, as it uses a local criteria based on cell relative angle.
