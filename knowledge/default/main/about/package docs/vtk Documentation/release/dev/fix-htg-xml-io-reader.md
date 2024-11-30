## Fix HTG XML IO Writer

vtkXMLHyperTreeGridWriter takes DepthLimiter parameter of HyperTreeGrid into account only for data set major version 2 of file output.

Extension of testing to cover this aspect of write reduction.
