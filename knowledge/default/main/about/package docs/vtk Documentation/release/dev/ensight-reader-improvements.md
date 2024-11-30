## EnsightCombinedReader: Performance improvements pass

Improve performances of the new vtkEnSightGoldCombinedReader in various ways, especially when reading large binary files containing nfaced/tetrahedron cells:
* The tetrahedron cell-building logic now uses a tetrahedron-specific vtkUnstructredGrid::InsertNextCell call
* Tetrahedron cells connectivity data are read as one block rather than cell-by-cell
* Add new "skip" methods to vtkEnSightDataSet which implement dedicated logic to ignore file cell sections. The logic is duplicated a bit from the equivalent reading methods at the benefit of much faster parsing during the RequestInfo pass (to get the parts names)
* Fix an int overflow that could occur while seeking ahead in large files
