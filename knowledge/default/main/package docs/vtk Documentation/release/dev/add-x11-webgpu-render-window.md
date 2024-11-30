## Add New X WebGPU Render Window For Linux

You can now run VTK applications with the experimental webgpu
backend on Linux desktops using the new object factory override
`vtkXWebGPURenderWindow`. This class is automatically enabled
as a default override on Linux desktop at build time. By default,
this render window prefers Vulkan backend a high-performance graphics
adapter.

All you need to use it is configure and build VTK with dawn.
You can enable webgpu with `VTK_ENABLE_WEBGPU=ON` and provide
the paths to Google's dawn source and binary directories.
