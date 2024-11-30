## vtkAxisActor2D improvements

vtkAxisActor2D has different modes to compute tick positions and number of labels.
Consistency has been improved between modes in several ways:
 * the number of labels always matches the number of ticks
 * the displayed labels text always matches the ticks position
 * the "SnapLabelsToGrid" mode is created to place ticks on rounded values
