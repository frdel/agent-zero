## OpenXR: Add support for depth reprojection

Depth information is useful for augmented reality devices, such as the Hololens 2.
When enabled, the depth texture of the render window is submitted to the runtime. The runtime will use this information increase hologram stability.
Check out vtkOpenXRManager::SetUseDepthExtension for more informations!
