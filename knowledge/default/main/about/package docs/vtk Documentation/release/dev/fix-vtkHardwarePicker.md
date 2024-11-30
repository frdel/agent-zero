## Ensure vtkHardwarePicker returns the ID from the closest node

Previously HardwarePicker would take the path returned by
vtkRenderer::PickPropFrom, which returns the closest picked node
(lowest z buffer value).  PickPropFrom also returns a vtkSelection with
a list of all picked nodes.

HardwarePicker would then extract the composite index and
PointId/CellId from the first vtkSelectionNode in the returned
selection, which was not guaranteed to be the closest picked node,
resulting in incorrect ids being used.

Further, this id would be used in ComputeIntersectionFromDataSet to
compute the pick position and pick normal.

This is fixed by updating vtkRenderer::PickProp to guarantee that
the first selection node will be the closest picked node (that is,
the node for the returned prop).
