## Refactor the `vtkRedistributeDataSetFilter` for more modularity

The `vtkRedistributeDataSetFilter` now utilises a strategy pattern `vtkPartitioningStrategy` for encapsulating the partitioning algorithm to use when redistributing a data set. You can now change the partitioning strategy dynamically at runtime.

The previous strategy hardcoded into the `vtkRedistributeDataSetFilter` has been refactored into the `vtkNativePartitioningStrategy` class (inheriting from `vtkPartitioningStrategy`). No novel strategies are included in this development.

> WARNING: The method `vtkRedistributeDataSetFilter::SplitDataSet` has changed signature and been made private. It no longer made any sense in the generic implementation proposed in this development.
