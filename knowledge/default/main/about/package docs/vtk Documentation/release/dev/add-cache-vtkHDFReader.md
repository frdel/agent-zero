## Support for `vtkPartitionedDataSet` outputs in the `vtkHDFReader`

The `vtkHDFReader` can now output `vtkPartitionedDataSet`s when reading `vtkPolyData` or `vtkUnstructuredGrid`s. To do so, one may simply deactivate the new `MergeParts` property of the reader (`true` by default for backwards compatibility).

## Support for caching read data in the `vtkHDFReader` to avoid re-reading it at later time steps

Using the new `UseCache` property of the `vtkHDFReader` you can cache data internally in the reader to avoid re-reading it later. If the cache is active, it should be populated with the data read in on the previous update of the reader. On subsequent update calls, the reader will use the data already cached if it corresponds to the data requested. If the reader needs to read from the file, it does so and then updates the cache entry with the new data. The cache granularity is at the individual array level for maximal performance gains.

For the best memory performance when using the cache, the new `MergeParts` option should be turned off. This is because, in the context of reading `vtkPolyData` or `vtkUnstructuredGrid`s, the data is already partitioned in the file and thus read per piece. The cache stores individual pieces of arrays to avoid re-reading them. When merging the parts, the data effectively gets concatenated and copied into the new merged structure and thus exists duplicated in the output and in the cache. This is not the case when `MergeParts` is turned off and the arrays can be referenced both in the cache and in the output at practically zero memory cost.
