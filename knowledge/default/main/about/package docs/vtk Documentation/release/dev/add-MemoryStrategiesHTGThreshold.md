## `vtkHyperTreeGridThreshold` now supports multiple strategies for representing its output in memory

The `vtkHyperTreeGridThreshold` now exposes a `SetMemoryStrategy` method for choosing the structure of its output in memory:
* `MaskInput` (=0, default): shallow copy and mask the input to describe the threshold
* `CopyStructureAndIndexArrays` (=1): generate an new HTG in the output with cell arrays indexed on the output using `vtkIndexedArray`s
* `DeepThreshold` (=2): generate a completely new HTG describing the threshold of the input from scratch
