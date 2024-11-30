## Hyper Tree Grid Ghost Cells support

Hyper Tree Grid Ghost Cell Generator now supports multi-components array to be transferred between MPI ranks.

The class has been reorganized internally, providing more precise debugging log and progress feedback.
Mask support has been improved and optimized: refined masked cells will not send their full tree decomposition anymore.

Also, new filter `vtkHyperTreeGridExtractGhostCells` and `vtkHyperTreeGridRemoveGhostCells` has been created to extract
and remove ghost cells for a HTG, similarly to what `vtkExtractGhostCells` and `vtkRemoveGhosts` does for other data types.

# Use vtkCompositeArray in vtkHyperTreeGridGhostCellsGenerator

The vtkHyperTreeGridGhostCellsGenerator now uses vtkCompositeArray to store cell data information.
This allows to store a shallow copy of the existing cell data instead of building a complete new array.
