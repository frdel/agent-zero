## New `vtkFDSReader` for Fire Dynamics Simulator output

You can now read in output from the Fire Dynamics Simulator (FDS, https://pages.nist.gov/fds-smv/) into VTK. The reader is based on reading the `*.smv` meta-data file to orchestrate the reading of all the other files. It supports:

* Grids: reading in the extents of the entire simulation domains
* Devices: reading in data from so called "devices" and representing it as point data
* HRR: reading in globally integrated data as a table
* Slices: subsets of the entire grids with point data on them
* Boundaries: subsets of the grids that represent obstacles or boundaries in the simulation

The output of the reader is a `vtkPartitionedDataSetCollection` divided into the sections above.
