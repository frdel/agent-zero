## Support writing VTKHDF files

Previously, only reading VTKHDF files from VTK was supported. We introduce `vtkHDFWriter`,
capable of writing sequentially VTK data structures to disk in the VTKHDF format.
So far, the writer is capable of writing static and time-dependent data for vtkPolyData, vtkUnstructuredGrid
and their vtkPartitionedDataset versions.

vtkPartitionedDataSetCollection and vtkMultiBlockDataSet are also supported, without temporal support.
These composite types have the option to be written either in a single standalone file,
or as a collection of files: one describing the composite assembly structure, and
every other containing the data relative to a non-composite leaf.
Both are considered equivalent by the reader.

Temporal datasets and vtkPartitionedDataset can also be written in separate files,
one for each time step or partition, with a main file that references their data

Distributed writing is supported for distributed data with pieces written by different processes
in individual files, and grouped as a partitioned dataset by the rank 0 using virtual datasets
when pieces are poly data or unstructured grid. Temporal data and static meshes are also supported in distributed writing.

User can compress chunked dataset thanks to the CompressionLevel option.
