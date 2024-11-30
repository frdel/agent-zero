## vtkPolyDataNormals: Split into separate classes

`vtkPolyDataNormals` used to be a single class that performed, splitting of strips, orienting polygons,
splitting sharp edges, and computing normals. This class has been split as follows to make
it easier to use and understand.

1. `vtkTriangleFilter` now has an option to `PreservePolys`, so that only strips can be split.
2. `vtkOrientPolyData` is a new class that orients polygons.
3. `vtkSplitSharpEdgesPolyData` is a new class that splits sharp edges.
4. `vtkPolyDataNormals` now only computes point and cell normals.

The new classes are more efficient and easier to use and read than the old `vtkPolyDataNormals` class.

Additionally, `vtkAbstractCellLinks` now also have `ShallowCopy` which is used to copy the cell links
to avoid copying/rebuilding them.

Moreover, `vtkStaticCellLinks`'s BuildLinks for `vtkPolyData` has been fixed and multi-threaded.

Finally, `vtkPolyData` when `Editable` is Off, `vtkStaticCellLinks` is used to create the cell links.
