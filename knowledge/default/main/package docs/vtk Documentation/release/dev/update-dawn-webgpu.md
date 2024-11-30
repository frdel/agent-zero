# Update Dawn/WebGPU API in the WebGPU backend

- `WGPUShaderModuleWGSLDescriptor::source` has now been renamed to `WGPUShaderModuleWGSLDescriptor::code`.
- `SetDeviceLostCallback`(deprecated by webgpu) has been removed in favor of `WGPUDeviceDescriptor::deviceLostCallback` member.
- `dawn::native::GetAdapter` (deprecated by dawn) has now been renamed to `dawn::native::EnumerateAdapters`.
- `wgpu::RenderBundleEncoder::colorFormatsCount` (deprecated by webgpu) has now been renamed to `colorFormatCount`. However, emscripten still uses the version of webgpu which shipped with `colorFormatsCount`, so in webassembly, `colorFormatsCount` continues to be used. We will change this after emscripten updates it's webgpu headers.
