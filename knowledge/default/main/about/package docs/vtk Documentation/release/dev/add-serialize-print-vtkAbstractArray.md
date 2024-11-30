# Add methods to printand serialize values of a vtkAbstractArray

You can now print the values of a `vtkAbstractArray` to a stream object by invoking
`PrintValues(stream)`.

Ex:
```c++
vtkNew<vtkFloatArray> array;
array->InsertNextValue(1.0);
array->PrintValues(std::cout);
```

You can also serialize the values of a `vtkAbstractArray` into `json` with
`nlohmann::json vtkAbstractArray::SerializeValues()`
