## Add CONVERGE CFD CGNS reader

A new reader for CGNS files produced by CONVERGE CFD (`.cgns` extension) is now available.

Mesh, boundaries and parcels are read and stored as partitioned datasets
of a partitioned dataset collection to manipulate them separately.

The module `VTK::IOCGNSReader` is required to use this reader.
