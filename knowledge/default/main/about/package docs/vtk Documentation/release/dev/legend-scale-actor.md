## vtkLegendScaleActor improvements

vtkLegendScaleActor has been improved in several ways:
- The axes appearance can be configured using a vtkProperty2D
- In non-adjusted mode, the number of horizontal and vertical ticks can be configured
- Label values can be formatted using fixed-point or scientific notation in addition to the default formatting
- `XY_COORDINATES` was replaced by a more generic `COORDINATES`, where main axis is automatically found.
- In coordinates mode, an `Origin` can be set to shift the coordinates on each axis.
- The full grid can optionnally be displayed
