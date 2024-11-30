# vtkConduitSource and ConduitToDataObject
## ConduitToDataObject
Move the Conduit to DataObject API outside of the vtkConduitSource.
This last one is now focused on the vtkAlgorithm part and internally
uses the new API to create the output data object.

## Add channel field data at partition level
The `catalyst/channel/<channelName>/data/state/fields/` conduit node
is intended to contain field data.
This used to be added only on the root level, and thus the value
from only one rank is used.

We now add the field data at the leaf level of the PartionedDataSet,
i.e. on the concrete dataset.
Now each partition has its own value, and the array is not partial anymore.
