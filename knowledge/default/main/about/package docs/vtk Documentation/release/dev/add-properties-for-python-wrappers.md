# Add properties for python wrappers

The properties of a VTK object can now be accessed in a pythonic style.
Ex:

```python
i = vtk.vtkImageData()
print(i.dimensions) # prints (0, 0, 0)
i.dimensions = [2, 2, 3]
print(i.dimensions) # prints (2, 2, 3)
print(i.reference_count) # prints 1
```
