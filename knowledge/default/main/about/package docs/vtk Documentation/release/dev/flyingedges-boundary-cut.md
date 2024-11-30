## vtkFlyingEdgesPlaneCutter on min Boundary

When cutting an image data with a plane on a min Boundary,
the vtkFlyingEdgesPlaneCutter now returns the actual intersection
instead of an empty polydata.
See #19225 for the details
