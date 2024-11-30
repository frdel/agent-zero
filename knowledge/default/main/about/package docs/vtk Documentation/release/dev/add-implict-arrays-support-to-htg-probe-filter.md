## Add implicit array support to HTG probe filter

vtkHyperTreeGridProbeFilter now exposes the UseImplictArray option.
When on, the filter will use indexed arrays internally to improve the memory consumption of the filter,
at the price of a higher computational cost.

This option is disabled on vtkPHyperTreeGridProbeFilter until vtkHyperTreeGrid fully supports global IDs.
