## vtkModule-kit-target-leaks

The `vtk_module_link` CMake module API learned the `NO_KIT_EXPORT_IF_SHARED`
argument to prevent exporting of mentions of imported targets coming from a
`vtk_module_find_package(PRIVATE_IF_SHARED)` call.
