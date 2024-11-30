# Supported Hardware

VTK can integrate with a number of specialized visualization hardware including:

- [Looking Glass](https://lookingglassfactory.com/), see the latest blog post
  [here](https://www.kitware.com/looking-glass-factory-expands-reach-into-rd-labs-with-new-holographic-kitware-integrations).
  The integration is achieved using an
  [external](https://github.com/Kitware/LookingGlassVTKModule) vtk module that leverages
  the display's SDK.
- Virtual Reality headsets like [Oculus](https://www.oculus.com)  and
  [VIVE](https://www.vive.com) as described in
  [this](https://www.kitware.com/using-virtual-reality-devices-with-vtk) post
  via the {bdg-primary-line}`VTK::RenderingOpenVR` module.
- Augmented Reality headsets like
  [Hololens](https://www.microsoft.com/en-us/hololens) as demonstrated
  [here](https://www.kitware.com/stream-vtk-to-the-hololens-2) via the
  {bdg-primary-line}`VTK::RenderingOpenXRRemoting` module.
- Augmented Reality displays like [ZSpace](https://zspace.com/) via its
  ParaView integration as demonstrated
  [here](https://www.kitware.com/zspace-device-support-coming-to-paraview).
