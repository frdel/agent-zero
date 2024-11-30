## vtkCellArray default storage type is configurable at runtime

The internal storage type of vtkCellArray can be changed dynamically
between 32bit and 64bit sizes. Previously, the default storage size
was set to match the size of vtkIdType. By adding the static methods
`SetDefaultStorageIs64Bit()` and `GetDefaultStorageIs64Bit()`, this
default can now be changed at runtime.

This supports a use case where most models use indices that fit inside
32bit storage, saving memory, but some large models need 64bit indices,
and that can be detected at load time. Then the default can be switched
to 64bit storage, and downstream filters will use the new default.
