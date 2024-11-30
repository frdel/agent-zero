## vtkPolygon: EarCutTriangulation function change.

``vtkPolygon`` has a function EarCutTriangulation that now use a short path to generate quad triangulation.

This **SimpleTriangulation** is consistent  with previous earcut algorithm as the same triangles will be built.
It will also take care of arrowhead quads properly.
For performance reasons, the internal index order of the triangle points generated will differ from the previous algorithm.
Indeed, the new algorithm will not have the more concave corner as first point inside the generated triangle.
External filters that depends on an internal point order in each triangulated quad may have there output slightly changing.
