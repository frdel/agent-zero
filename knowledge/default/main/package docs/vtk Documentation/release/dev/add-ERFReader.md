## New `vtkERFReader` for ERF HDF5 File Format

You can now read ERF HDF5 file into VTK. It is based on the version 1.2 of the ERF HDF5 spec.
It supports:

* Reading a selected stage.
* Reading the 'constant' group.
* Reading the 'singlestate' group.

The output of the reader is a `vtkPartitionedDataSetCollection` composed of multiple unstructured grid for the 'constant' or 'singlestate' group.
