# `vtk_module_find_package(PRIVATE_IF_SHARED)`

Modules may now find packages with the `PRIVATE_IF_SHARED` argument to indicate
that the install will not actually mention the target if the target is built as
a shared library.
