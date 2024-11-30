# Memory Statistics For WebGPU Rendering Backend

You can now view detailed information about the GPU memory usage
of individual textures and buffers by setting the `VTK_WEBGPU_MEMORY_LOG_VERBOSITY`
environment variable or specifying a `vtkLogger::Verbosity` value to
`vtkWebGPUConfiguration::SetGPUMemoryLogVerbosity`.
