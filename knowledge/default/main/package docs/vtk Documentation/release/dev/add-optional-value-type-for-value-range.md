## Add optional value type for ValueRange

You can now force a value type for the `ValueRange` of a generic data array.
You can also get a pointer to the underlying data with the `ValueRange::data()` member function. This allows code in VTK
which used `GetPointer(0)` on an array under the assumption that it was available as `vtkGenericDataArrayTemplate` or derived from it.
This is helpful when all you have is a `vtkDataArray` and the knowledge of underlying data type.

Ex:
```c++
vtkNew<MyCustomDataArrayThatIsNotDerivedFromAoSDataArrayTemplate<vtkTypeUInt32>> arr;
arr->SetNumberOfValues(2);
arr->FillValue(0);
auto range = vtk::DataArrayValueRange<1, vtkTypeUInt32>(arr);
static_assert(std::is_same<typename vtk::detail::StripPointers<decltype(range.data())>::type, vtkTypeUInt32>::value); // always true.
static_assert(std::is_same<typename decltype(range[0]), vtkTypeUInt32>::value); // always true.
```
