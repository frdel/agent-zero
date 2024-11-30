## Add the vtkCriticalTime filter

Given an input that changes over time, the `vtkCriticalTime` filter generates a new
data array containing time step values. These values correspond to the time at which a specified
threshold criterion has been met for a given point/cell array (at each point/cell respectively).

To do so, the filter needs to process all available timesteps. The output of the filter in not temporal.

Like in the `vtkThreshold` filter, the threshold criterion can take three forms:
1) greater than a particular value;
2) less than a particular value;
3) between two values.
