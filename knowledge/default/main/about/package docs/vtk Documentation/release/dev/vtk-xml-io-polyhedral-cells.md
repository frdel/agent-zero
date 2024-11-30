## VTK XML I/O update to support new vtk Polyhedral cell storage

### New XML layout for polyhedron storage

When storing polyhedral cells, the file follows the in-memory layout.
Four arrays are then requires to build `vtkCellArray`  (in the same way it is already done for classical cell connectivity.

So here are the definition arrays for polyhedrons:
* **face_connectivity**: the points connectivity of each faces. All the faces’ point lists are concatenated together
* **face_offsets**: second array specifies the offset into the face array for the end of each face
* **polyhedron_to_faces**: the face list of each polyhedron cells.
* **polyhedron_offsets**: second array specifies the offset into the polyhedron cells for all cells

It replaces the previous arrays:
* **faces**
* **faceoffsets**

### Backward compatibility

Previous version of polyhedron VTK XML files are supported in reading mode.
In writing mode, if the file does not have polyhedron cells the file will be readable by older VTK version.
Support for writing an older version of the polyhedron XML storage is not implemented.
Thus when saving an Unstructured grid with polyhedron, it will not be possible to read it back with an older VTK version.
