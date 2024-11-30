## Cell Grid Data-object Fixes

The registration of new cell types and query-responders could cause
issues at startup (in static builds where the order of initialization
of variables such as STL containers is not guaranteed) and at
shutdown (where registered responders appear to be leaks if
vtkDebugLeaks is finalized before vtkCellGridResponders is; or
similarly if vtkFilteringInformationKeyManager is finalized while
vtkCellGridResponders holds objects referencing keys).
These issues have been addressed by changing how initialization
allocates the STL container and adding finalizers to force the
order in which classes are destroyed.
