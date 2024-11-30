## Add a magnitude option to vtkThreshold

You can now use input array's magnitude values for thresholding data.
To do so, you just need to set the selected component (when on SELECTED
mode) as the number of component of the input array.

```cpp
// let's say you have a source with a 'Speed' array
// which has 3 components

vtkNew<vtkThreshold> threshold;
threshold->SetInputConnection(source->GetOutputPort());
threshold->SetInputArrayToProcess(0, 0, 0, 0, "Speed");

threshold->SetThresholdFunction(vtkThreshold::THRESHOLD_UPPER);
threshold->SetUpperThreshold(4.2);

threshold->SetComponentModeToUseSelected();
threshold->SetSelectedComponent(3); // Select magnitude
threshold->Update();
```
