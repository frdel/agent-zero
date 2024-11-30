## Virtual/Mixed Reality rendering improvements

Changes to the view frustum calculation address proper rendering, particularly by the hardware
accelerated volume mapper (`vtkGPUVolumeRayCastMapper`) when the head-mounted display (HMD) is
positioned inside the volume. The computation of the view frustum was corrected by ensuring that the
appropriate eye transform matrices are accounted for when the VR camera is tracking the HMD.

### Deprecation

The following APIs were deprecated:

- `vtkVRRenderWindow::SetTrackHMD()`
- `vtkVRRenderWindow::GetTrackHMD()`

Developers should instead rely on the new VR camera specific tracking flag:

- `vtkVRCamera::SetTrackHMD()`
- `vtkVRCamera::GetTrackHMD()`

### References

- https://gitlab.kitware.com/vtk/vtk/-/issues/19123
- https://github.com/KitwareMedical/SlicerVirtualReality/issues/125
