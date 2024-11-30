## vtkIntegrateAttributes: Multithread using vtkSMPTools

``vtkIntegrateAttributes`` has been multithreaded using vtkSMPTools.

Also, ``vtkDataSet`` now has a function named ``GetMaxSpatialDimension`` that
returns the maximum spatial dimension of the dataset, which is the maximum cell dimension
of the dataset.
