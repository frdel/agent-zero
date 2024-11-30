## WGPUConfiguration initialization refactor in vtkWebGPUComputePipeline

The `vtkWebGPUComputePipeline` constructor does not initialize its `WGPUConfiguration` anymore.

This moves the request of the device (blocking operation) to the first call on the `vtkWebGPUComputePipeline`
that requires the device if a `WGPUConfiguration` wasn't manually given beforehand.
