## Integer API for vtkDataArray

There has been a long-standing need for access to integer
array data without casting the array to its storage type.

The `GetTuple()` and `SetTuple()` methods of `vtkDataArray` provide
double-precision floating-point access to arrays regardless of their
storage type.
Similarly, the `GetTypedTuple()` and `SetTypedTuple()` methods that
are specific to each array subclass provide array access in the
native storage format but require casting the array to its concrete type.
However, there was no method to reliably fetch large integer values
(such as connectivity entries or global point/cell IDs) without
macros or templated code, which often requires a significant
investment of developer time.

The floating-point API only provides 52-bits for integer values,
and in many cases 64-bit integer data would exceed this because
upper bits are used as flags modifying entries in less-signifcant bits.

Now, `vtkDataArray` provides the following methods you can use
to fetch and store tuples:

```cpp
void GetIntegerTuple(vtkIdType tupleIdx, vtkTypeInt64* tuple);
void SetIntegerTuple(vtkIdType tupleIdx, vtkTypeInt64* tuple);

void GetUnsignedTuple(vtkIdType tupleIdx, vtkTypeUInt64* tuple);
void SetUnsignedTuple(vtkIdType tupleIdx, vtkTypeUInt64* tuple);
```

These methods require you to pass in a pointer to a 64-bit integer array
large enough to hold an entire tuple of values.

You are still encouraged to use vtkSMPTools with templated workers,
`vtkArrayDispatch`, or the legacy `vtkTemplateMacro` where speed is required
but these methods make prototyping much simpler.
