# Accept keyword arguments in constructor for python wrapped VTK classes

In python, you can now initialize the properties of a wrapped VTK class through specifying
keyword arguments in the constructor.

Ex:

```python
s = vtkSphereSource(center=(1, 0, 0), generate_normals=False, radius=10, theta_resolution=20)
e = vtkElevationFilter(low_point=(1, 0, -10), high_point=(1, 0, 10), input_connection=s.output_port)
e.Update()
print(e.output.point_data.scalars.range) # prints (0.0, 1.0)
```
