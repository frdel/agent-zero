## Improvements related to vtk Polyhedral cell storage

###  Storing faces as vtkCellArray

When storing face information for polyhedral cells, `vtkUnstructuredGrid` uses a `vtkIdTypeArray` in a special format that looks awfully similar to how `vtkCellArray` used maintain its internal storage.
The new internal storage simply changes it to using `vtkCellArray` instead.
That will allow us to use a non-interleaved storage for faces. Together with using a `vtkCellArray` for `FaceLocations`  the one-2-many relationship can be easily preserved without resorting to custom layout used by the `Faces` array.

So here's the current storage structure:
* **Connectivity** (`vtkCellArray`): simply stores point ids for all points for each polyhedral element
* **Faces** (`vtkCellArray`): each element defines a polygonal face. The indices per element directly refer to point ids.
* **FaceLocations** (`vtkCellArray`): each element identifies a polyhedral cell. The indices per element reference face defined in the **ElementFace** array.


Contrast this with how this information was previously stored:
* **Connectivity** (`vtkCellArray`): simply stores point ids for all points for each polyhedral element (same as in the new proposal)
* **(Legacy)Faces** (`vtkIdTypeArray`): an interlaved array of the form `(numCellFaces, numFace0Pts, id1, id2, id3, numFace1Pts,id1, id2, id3, ...)`
* **(Legacy)FaceLocations** (`vtkIdTypeArray`): offset array into **(Legacy)Faces** array indicating where the faces for a corresponding cell are stored


### Backward compatibility

To ensure a nice transition to the new storage, some old API are kept.
More precisely the method `void SetCells(vtkUnsignedCharArray* cellTypes, vtkCellArray* cells, vtkIdTypeArray* faceLocations, vtkIdTypeArray* faces);` from vtkUnstructuredGrid is deprecated but can still be used. In this case a copy of faceLocations and faces data will be done.
Another case are the `GetFaces` and  `GetFaceLocations` methods. They are still available  but an internal cache with the old internal layout is used.
It means that they should be considered as read only methods and not be relied on to change internal data of vtkUnstructuredGrid.
The caching process may impact a bit performance.

The `FaceConn` and `FaceLocs` internal arrays of `vtkUnstructuredGridCellIterator` are no longer available as `vtkIdTypeArray`. This may break your subclasses if you rely on them directly and not on the exposed API of `vtkUnstructuredGridCellIterator`. A solution to keep using them in subclasses is to define them directly in subclasses and handle their logic.


### Compatibility with Conduit

The new layout is much closer to how Conduit store its polyhedral cell information.
Thus, some gain should be expected on the long run.
