## vtkWebAssemblyWebGPURenderWindow: Support wasm64 and web workers

`vtkWebAssemblyWebGPURenderWindow` is a new class that now uses Emscripten HTML5 and WebGPU API for device and surface creation instead of SDL2. This update ensures smoother operation in wasm64 and web worker environments.

What this means: You can now completely offload VTK WebGPU rendering within a web worker inside a browser.

The new `vtkWebAssemblyWebGPURenderWindow` is now the default factory override
of `vtkRenderWindow` for WebGPU in webassembly. It is meant to replace the `vtkSDL2WebGPURenderWindow`, which will soon be deprecated.
