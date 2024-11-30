## Use cell mask to compute HyperTreeGrid bounds

The vtkHyperTreeGrid::GetBounds() now returns the correct bounds of the htg without masked cells.
The old behavior that was using grid bounds is still available under
the name vtkHyperTreeGrid::GetGridBounds().
