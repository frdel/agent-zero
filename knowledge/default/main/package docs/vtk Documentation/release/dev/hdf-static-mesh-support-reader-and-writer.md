## Support static mesh for HDF format in HDF Reader & Writer

Add static mesh support for the HDF format in the Reader & Writer.

### Reader specific usage details

To enable static mesh using the Reader the following properties must be set :

- `MergeParts = false`
- `UseCache = true`
  The reader supports the following input types with static mesh enabled :
- `vtkPolyData`
- `vtkUnstructuredGrid`

The reader will always output a `vtkPartitionedDataset`
The static mesh support requires `MergeParts` to be set to false, leading to a `vtkPartitionedDataset` output with atleast 1 partition of the above types.Otherwise, the reader internally merge all parts using a `vtkAppendDataSet` filter which is not static mesh compliant (yet)

### Writer specific usage details

The writer can't process partitioned data as input yet,
so the static mesh support isn't implemented for `vtkPartitionedDataset` as well.
