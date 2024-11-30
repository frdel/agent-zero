## vtkImageData/vtkRectilinearGrid/vtkStructuredGrid: Improve performance using structured Points, Cells, CellTypes

`vtkStructuredPointArray<ValueType>` has been implemented to enable fast query of structured points.

`vtkStructuredCellArray` has been implemented to enable fast query of structured cells. `vtkStructuredCellArray` and
`vtkCellArray` have `vtkAbstractCellArray` as their parent class.

`vtkStructuredPointArray<ValueType>`, `vtkStructuredCellArray`, and `vtkConstantArray<int>` are used to implement
the following three functions in `vtkStructuredData`.

1) `vtkSmartPointer<vtkPoints> GetPoints(vtkDataArray* xCoords, vtkDataArray* yCoords, vtkDataArray* zCoords,
   int extent[6], double dirMatrix[9])`
2) `vtkSmartPointer<vtkStructuredCellArray> GetCellArray(int extent[6], bool usePixelVoxelOrientation)`
3) `vtkSmartPointer<vtkConstantArray<int>> GetCellTypesArray(int extent[6], bool usePixelVoxelOrientation)`

The above functions are used to build the structured Points, Cells, and CellTypes
for `vtkImageData`/`vtkRectilinearGrid`,
and to build the structured Cells, and CellTypes for `vtkStructuredGrid`.

Using these structured classes, the performance of the following functions has been optimized.

1) `GetPoint` for `vtkImageData`/`vtkRectilinearGrid`
2) `GetCellBounds` for `vtkImageData`/`vtkRectilinearGrid`/`vtkStructuredGrid`
3) `GetCellSize` for `vtkImageData`/`vtkRectilinearGrid`/`vtkStructuredGrid`
4) `GetCellType` for `vtkImageData`/`vtkRectilinearGrid`/`vtkStructuredGrid`
5) `GetCellPoints` for `vtkImageData`/`vtkRectilinearGrid`/`vtkStructuredGrid`
6) `GetCell` for `vtkImageData`/`vtkRectilinearGrid`/`vtkStructuredGrid`

`vtkImageData` and `vtkRectilinearGrid` now check for cell visibility when using the `GetCell`, `GetCellSize`, and
`GetCellType` functions. Also they have blanking, and un-blanking capabilities of points and cells. Thanks to these
changes, the implementation of `vtkUniformGrid` has been greatly simplified.

Since `vtkImageData` and `vtkRectilinearGrid` now have structured points, `vtkDataSet` has a function `GetPoints` that
returns the structured/explicit points, if present, else it creates an internally copy of the points using `GetPoint`
and returns that. Thanks to this addition `void vtkRectilinearGrid::GetPoints(vtkPoints* points)` has been deprecated.

Additionally, `vtkImageData`/`vtkRectilinearGrid`/`vtkStructuredGrid` now also have `GetCells` and `GetCellTypesArray`
functions.

To effectively utilize the structured Points. `vtkDataArrayRange` now has `GetTuple` and `SetTuple` functions
that can efficiently query the structured Points when it has been dispatched.

To that end, the following classes/functions have been updated to efficiently query the structured Points, Cells, and
CellTypes.

1) `vtkTableBasedClipDataSet`
2) `vtkStructuredDataPlaneCutter`
3) `vtkExtractGeometry`
4) `vtkExtractCells`
5) `vtkElevationFilter`
6) `vtkPoints::GetPoints`
7) `vtkBoundingBox::ComputeBounds`
8) `vtkIOSSModel::StructuredPointsOperator`

Moreover, in `vtkStructuredDataPlaneCutter` when `vtkFlyingEdgesPlaneCutter` is used, if scalars are not present, then
a constant array is created instead of using `vtkElevationFilter` for better performance. If ghosts are present,
and InterpolateAttributes is on then `vtkFlyingEdgesPlaneCutter` is used and the ghosts are removed afterward.

Finally, in `vtkContourFilter`, when `vtkFlyingEdges3D` or `vtkSynchronizedTemplates3D` is used, if ghosts are present.
then ghosts will be removed afterward.
