# Fix GetShiftedLevelZeroIndex method HyperTreeGrid

The GetShiftedLevelZeroIndex method signature for HyperTreeGrid has been modified to better account for negative shifts.
The vtkRandomHyperTreeGridSource has been extended to support 2D cases beyond the classic 2D XY case (YZ and ZX).
