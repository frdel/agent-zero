## String tokenization

The `vtkStringManager` class caused issues for static builds of VTK;
because `vtkStringToken` holds a class-static instance of the string
manager, static builds would crash on some platforms during
initialization because

1. The order of initialization of globals is not guaranteed; and
2. For some platforms, when a static library with globals (e.g.
   library A) is linked to other static libraries (e.g., libraries
   B and C), each of the downstream libraries (B and C) would
   instantiate a separate copy of the upstream's (A) globals,
   causing missing entries and crashes.

Because of this, the string tokenization code has been moved into
a new third-party library (`ThirdParty/token`) which is forced to be
a dynamic library. This library also offers a function to fetch or
create singleton objects (since dynamic libraries do not have the
issues above) and VTK now uses it for globals holding `vtkCellGrid`
metadata.
