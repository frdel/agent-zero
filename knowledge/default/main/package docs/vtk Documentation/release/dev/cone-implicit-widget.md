# Implicit Cone Widget
## Extended vtkCone API
`vtkCone` now exposes new getters and setters for its axis and origin parameters. Changing those will automatically update the `vtkImplicitFunction`'s transform.

## Added a new Implicit Cone Widget
A new interactive implicit cone widget has been added. It represents an infinite cone parameterized by an axis, and angle between the sides of the cone and its axis, and an origin point. Users can manipulate the widget through controls similars to the cylinder widget ones.
Its underlying cone can be used in any filter relying on implicit functions (i.e. Clip).
