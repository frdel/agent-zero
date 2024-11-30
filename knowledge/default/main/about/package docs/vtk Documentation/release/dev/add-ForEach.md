## Introduce vtkForEach filter

vtkForEach and vtkEndFor are two newly introduced filters that works in
conjunction.  Their goal is to define a part of the pipeline to repeat. In
this matter, the `vtkForEach` uses a `vtkExecutionRange` to define a ranging
strategy. For now, it uses by default the `vtkTimeRange` range strategy that
loops over timesteps. In the future, other strategies using for examples blocks
of a composite data set may be added.
On the other end of the pipeline, the `vtkEndFor` uses
a `vtkExecutionAggregator` to process the result of each
iteration into a resulting dataset. For now, it uses by default the
`vtkAggregateToPartitionedDataSetCollection`, which stores each result in
a separate partition. Other strategies, that would append all data sets,
or generate a temporal one may be added later.

It is not possible to use nested `vtkForEach/vtkEndFor`. Such processing
would require to design a specific range in the current state. Successive
loops are supported.
