## vtkWebAssemblyRenderWindowInteractor: Support wasm64 and web workers

`vtkWebAssemblyRenderWindowInteractor` now uses Emscripten HTML5 API for event handling
instead of using SDL2. This update ensures smoother operation in wasm64 and web worker environments.

What this means: You can now completely initialize and start processing events of a `vtkRenderWindowInteractor` within a web worker inside a browser.
