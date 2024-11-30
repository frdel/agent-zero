## Mask support for vtkRandomHyperTreeGridSource

You can now generate a pseudo random mask on a `vtkRandomHyperTreeGridSource`. This mask uses the same seed as the one used to generate the tree structure. It computes the cost of each node depending on the space it occupies in the scene and provides the information about the total masked fraction of the `HyperTreeGrid`. There is margin of error between the actual and target masked fraction, which depends on the number of tree and the number of children of each node.
