## Add Graphics Backend Preference Option For WebGPU Render Window

`vtkWebGPURenderWindow` now provides a way to choose a graphics backend
at runtime. The available backends vary on different operating systems.
Here are the available backends:
1. D3D11
2. D3D12
3. OpenGL
4. OpenGL ES
5. Metal
6. Vulkan

VTK pre-initializes the render window with a suitable default backend. They
are:
1. D3D12 on Windows
2. Metal on macOS
3. Vulkan everywhere else

In case a backend is unavailable, the webgpu implementation (Dawn) may fallback
to a suitable default or fail to return an adapter.

You may indicate preference like so:
```c++
vtkNew<vtkRenderWindow> renWin
// requests webgpu implementation for a D3D12 backend
renderWindow->SetBackendTypeToD3D12();
// Similarly,
// renderWindow->SetBackendTypeToD3D11();
// renderWindow->SetBackendTypeToOpenGL();
// renderWindow->SetBackendTypeToOpenGLES();
// renderWindow->SetBackendTypeToMetal();
// renderWindow->SetBackendTypeToVulkan();
//..
renderWindow->Render();
```
