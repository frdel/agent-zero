## Improve vtkGhostCellsGenerator

You can now generate points/cells global and process ids directly in the filter.
There are two new options to enable their generation.

The filter is also more efficient for pipelines requiring ghost data
synchronization. There is indeed a new option you can enable, that will try to
synchronize ghost data when there are already ghost, global ids, and process
ids arrays. This assumes that you want to synchronize ghost data, without
generating more ghost layers.
