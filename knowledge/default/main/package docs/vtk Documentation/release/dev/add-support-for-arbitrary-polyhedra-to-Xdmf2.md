Add support for arbitrary polyhedra to Xdmf2.

The Xdmf2 reader now works with geometries that contain arbitrary polyhedra;
i.e. cells with an arbitrary number and arrangement of faces.
The face connectivity is defined explicitly in the geometry description.

This replicates the same ability that exists in Xdmf3.
