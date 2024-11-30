## vtkPolyhedron: Protected Members and functions changes

``vtkPolyhedron`` had the following protected members' and functions' changes:

1. `PointIdMap` pointer is no longer a pointer, and it's now a private member.
2. `PointToIncidentFaces` is no longer a pointer of pointers, but a std::vector<std::vector<vtkIdType>>, and it's now
   a private member.
3. `ValenceAtPoint` point has been removed since it is no longer needed.
4. `GeneratePointToIncidentFacesAndValenceAtPoint` function has been deprecated in favor of `
   GeneratePointToIncidentFaces` function.
