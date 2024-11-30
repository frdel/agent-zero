## vtkModule-file-set-api

The `_vtk_module_add_file_set` internal API has been added to add file
sets to targets in a CMake-version portable way.

The `vtk_module_build` API has learned a new `USE_FILE_SETS` API to control the
usage of file sets for projects that are not yet ready to use them.
