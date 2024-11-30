## Improve vtkUniformGridAMR Selection Support

vtkExtractSelection now properly works for vtkUniformGridAMR subclasses.
This was achieved by Modifying vtkDataObjectTree to support vtkUniformGridAMR for CopyStructure, GetDataSet, SetDataSet.
Also when creating the hierarchy of a vtkUniformGrid, now all composite indices are in a level are included.
Finally, as we prepare to deprecate vtkMultiBlockDataSet, if the input is a vtkUniformGridAMR, vtkExtractSelection now
generates a vtkPartitionedDataSetCollection instead of a vtkMultiBlockDataSet. Also the following protected function
has been deprecated.
```
void CutAMRBlock(
vtkPlane* cutPlane, unsigned int blockIdx, vtkUniformGrid* grid, vtkMultiBlockDataSet* dataSet);
```
