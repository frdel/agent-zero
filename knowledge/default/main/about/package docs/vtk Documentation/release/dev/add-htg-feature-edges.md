## Add vtkHyperTreeGridFeatureEdges filter

Add a dedicated filter for hyper tree grids.
Unlike the vtkFeatureEdges filter, which operates on a vtkPolyData and generate feature
edges based on geometrical characteristics, the vtkHyperTreeGridFeatureEdges produces them
by iterating through the input vtkHyperTreeGrid directly.
Note that data on each edge is copied from the cell that created it. In the current implementation,
masked cells can create edges, so data can be irrelevant in such cases.
