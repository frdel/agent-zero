Extend 3D Tiles reader to:
- allow B3DM tiles
- support external tilesets
- enable applying textures
- fix a bug where only the first partition in a tile was loaded
- BREAKING_CHANGE: the reader produces a
  vtkPartitionedDataSetCollection instead of a vtkPartitionedDataSet.

These changes require the following  vtkGLTFReader improvements:
- using the GLTF reader to read an embedded GLB inside another file (the B3DM in this case)
- adding an option to GLTF to produce double points - this is needed for 3D Tiles
- fixing the way textures are exported so that the API wrapped in python
