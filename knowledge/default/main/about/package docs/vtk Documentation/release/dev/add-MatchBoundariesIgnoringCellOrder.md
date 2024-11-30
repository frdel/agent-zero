## Disable rendering of interior faces that are between cells of different order

### Motivation

Local refinement can produce meshes composed by different cell types and multiple degrees.So far, when two volumetric cells of different order are connected by their corners (for instance, a quadratic hexahedron next to a linear hexahedron ), the internal face is rendered and is not considered as a ghost cell.
One may want to hide the rendering of these internal faces for multiple reasons:
* When playing with transparency, we don't want to see some faces that can be located in the middle of the geometry.
* For big meshes, the rendering of the interior faces can drastically impact the performances.
So for this reason, we would like to optionally disable the rendering of internal faces.

### Implementation
In this work, the option MatchBoundariesIgnoringCellOrder is added to vtkUnstructuredGridGeometryFilter. The way it's work is that in InsertFace, if MatchBoundariesIgnoringCellOrder is activated, only the cell corners are used to check if two cells are superposed.
