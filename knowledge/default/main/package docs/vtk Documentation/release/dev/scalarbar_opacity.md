# Opacity function support in vtkScalarBarActor

The vtkScalarBarActor now supports accepting vtkPiecewiseFunction as a scalar opacity function in
addition the lookup table. This allows representing both color and opacity functions using the same
scalar bar actor.
