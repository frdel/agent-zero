## Fix missing IsParallelScope symbol for win32 static builds

Building packages against static VTK libraries with the MSVC compiler no
longer fails due to a missing symbol for vtkSMPToolsImpl::IsParallelScope.
