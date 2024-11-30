## New class to initialize webgpu device

You can now use `vtkWebGPUConfiguration` to create a webgpu device using an appropriate graphics backend and power preference.
The `vtkWebGPURenderWindow` and `vtkWebGPUComputePipeline` classes internally leverage `vtkWebGPUConfiguration` for device initialization
and cleanup.

You can now safely design complex applications leveraging multiple devices by instantiating and passing around
instances of `vtkWebGPUConfiguration` among any of `vtkWebGPURenderWindow` or `vtkWebGPUComputePipeline`.
