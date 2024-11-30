## Add vtkBatch/vtkBatches and improve vtkTablaBasedClipDataSet's performance

Batches are a concept that is used in several filters in VTK to enable multithreading.
`vtkBatch`/`vtkBatches` are 2 classes that encapsulate the concept of a batch.

The following filters/data structures have been updated to use `vtkBatch`/`vtkBatches`:

1. `vtkStaticFaceHashLinks`
2. `vtkExtractCells`
3. `vtkStructuredDataPlaneCutter`
4. `vtkPolyDataPlaneCutter`
5. `vtkPolyDataPlaneClipper`
6. `vtkTableBasedClipDataSet`

Additionally, the performance of `vtkTableBasedClipDataSet` has been improved by ~25%.

This has been achieved by using with the following ways:

1. Used `vtkBatches` for processing also the input points (instead of just the cells), which enables multithreading.
2. Reorganized the clip cases table, to enable the removal of several switch cases, and color based checks due to if
   inside out is on or off.
3. Used memcpy instead of for loops to copy point ids to the output cells for the output.
4. Created a fast path when a cell is kept or discarded and used the general path only when a cell is clipped.
