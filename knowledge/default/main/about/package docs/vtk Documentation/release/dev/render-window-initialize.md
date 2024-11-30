# Addition of RenderWindow::Initialize

Initialize() method meant to be overriden mainly by vtkWebGPURenderWindow for setting up the Device/Adapter before WebGPU compute pipelines objects need them.

This Initialize() method can be used by classes inheriting from vtkRenderWindow if some initialization is needed before the first Render() call.
