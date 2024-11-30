## Implicit Arrays are now available in Wrapping

The Implicit Array framework is based on vtkImplicitArray template
specialization on some backend.
Different backend already exist but are also templated on a concrete type.
For instance we have `vtkImplicitArray<vtkConstantImplicitBackend<double>>`,
aka `vtkConstantArray<double>`.
Because of this template declaration, wrapping was not enabled for those classes.

VTK now generates non-templated subclasses like `vtkConstantDoubleArray`
at build time for those implicit arrays instances, making them also available in python!

```python
from vtkmodules.vtkCommonCore import vtkAffineFloatArray
affineArray = vtkAffineFloatArray()
affineArray.ConstructBackend(1.2, 3.4)
```

Support includes `vtkConstantArray`, `vtkAffineArray`, `vtkCompositeArray` and `vtkIndexedArray`,
specialized for the following types:

  char, double, float, vtkIdType, int, long, short, signed char, unsigned char,
unsigned int, unsigned long, unsigned short

### Developers notes
For each `vtkMyBackendArray<T>` class, there is `vtkMyBackendTyped.h.in` and `vtkMyBackendTyped.cxx.in`
that are configured from vtkImplicitArrays.cmake.
The `.in` files should implements the `ConstructBackend` method and some typed getter
mainly through the `vtkCreateReadOnlyWrappedArrayInterface` macro.

The generated classes are added to the module public headers and sources.

By default a subclass of a given backend is instanciated for each type (see list above).
