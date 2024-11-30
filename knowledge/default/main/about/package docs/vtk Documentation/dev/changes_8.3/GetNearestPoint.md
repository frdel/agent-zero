# vtkPlotPoints::GetNearestPoint API Change

vtkPlotPoints::GetNearestPoint(const vtkVector2f& point, const vtkVector2f& tol, vtkVector2f* location)
has changed and has now a new optional argument segmentId.
The new signature is as follows :
vtkPlotPoints::GetNearestPoint(const vtkVector2f& point, const vtkVector2f& tol, vtkVector2f* location, vtkIdType* segmentId))

With VTK_LEGACY_REMOVE=OFF, calls and override of the old api still works for the time being.
