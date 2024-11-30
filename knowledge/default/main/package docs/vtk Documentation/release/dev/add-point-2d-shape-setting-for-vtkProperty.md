# Add new setting to specify 2D point shape in vtkProperty

You can now draw round points by calling the new `vtkProperty::SetPoint2DShape()` method
with a value of `vtkProperty::Point2DShapeType::Round`. The default value is `vtkProperty::Point2DShapeType::Square`.
Note that points will be rendered as spheres when `RenderPointsAsSpheres` is turned on irrespective
of the value of `Point2DShape`.

This feature is only implemented in the new WebGPU rendering module. The OpenGL module ignores
this setting.
