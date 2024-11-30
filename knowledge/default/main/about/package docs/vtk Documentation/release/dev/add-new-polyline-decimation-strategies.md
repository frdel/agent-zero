## Add new polyline decimation strategies

The `vtkDecimatePolylineFilter` has been refactored to use a strategy pattern.
It used a default strategy based on eulerian distances.
This change brings 2 new available strategies :
- `vtkDecimatePolylineAngleStrategy` which uses the angle between 3 consecutive points to perform the decimation.
- `vtkDecimatePolylineCustomFieldStrategy` which uses a specified `PointData` array to gather the values used for the decimation.

It is also possible to make custom strategies by inheriting  the `vtkDecimatePolylineStrategy` class.

The new default strategy for the `vtkDecimatePolylineFilter` is the `vtkDecimatePolylineDistanceStrategy` which implements the old eulerian distance computation.
