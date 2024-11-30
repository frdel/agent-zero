## Change vtkOrientPolyData seed face selection algorithm

A bug was found in the seed face cell selection algorithm used when orienting normals, when cells have the same x-component of their normal.

The algorithm has been changed to deal with this case by choosing a cell attached to the left-most (i.e. negative x-direction) point for which no cell attached to the leftmost point has any non-shared points on the left of it's plane.
