## Add Power Preference Option For WebGPU Render Window

`vtkWebGPURenderWindow` now provides a way to choose power preference
before initialization. The default preference is high-performance.

You may indicate preference like so:
1. High performance
```c++
vtkNew<vtkRenderWindow> renWin
// requests webgpu implementation for a high performance adapter
renderWindow->PreferHighPerformanceAdapter();
//..
renderWindow->Render();
```

2. Power savings
```c++
vtkNew<vtkRenderWindow> renWin
// requests webgpu implementation for a low-power adapter
renderWindow->PreferLowPowerAdapter();
//..
renderWindow->Render();
```
