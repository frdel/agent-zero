## vtkWebAssemblyOpenGLRenderWindow: Support wasm64 and web workers

`vtkWebAssemblyOpenGLRenderWindow` is a new class that now uses Emscripten HTML5 and WebGL API for OpenGL context creation instead of SDL2. This update ensures smoother operation in wasm64 and web worker environments.

What this means: You can now completely offload VTK OpenGL rendering within a web worker inside a browser.

The new `vtkWebAssemblyOpenGLRenderWindow` is now the default factory override
of `vtkRenderWindow` for OpenGL in webassembly. It is meant to replace the `vtkSDL2OpenGLRenderWindow`, which will soon be deprecated.
