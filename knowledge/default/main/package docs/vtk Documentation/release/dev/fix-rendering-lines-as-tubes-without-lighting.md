## Fix `Rendering Lines As Tubes" without lighting

Rendering lines as tubes with the `vtkOpenGLPolyDataMapper` without lighting enabled was causing issues in the fragment shader compilation.
This fixes it by adding an additional check. The feature is now disabled if no lights are present or if lighting is disabled through `vtkProperty`.
Rendering lines as tubes relies on lights to take effect since tubes are simulated with lighting and normals (when rendering both surface and edges).
