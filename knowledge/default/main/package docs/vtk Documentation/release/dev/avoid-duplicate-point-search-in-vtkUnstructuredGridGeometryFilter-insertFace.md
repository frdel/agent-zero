### Avoid some duplicate point searches in vtkUnstructuredGridGeometryFilter::InsertFace

Slightly improve speed of vtkUnstructuredGridGeometryFilter::InsertFace
* One point check was redundant and has been removed.
* Stop the search on the second part of the algo if the found flag is false.
