## SDL2 usage is now disabled by default

VTK has now deprecated the use of SDL2 in the render window and interactor classes. The cmake option `VTK_USE_SDL2` will soon be removed.
If your application relies on object factory mechanism (most common usage), there is nothing you need to do besides removing `VTK_USE_SDL2`
from your build settings.

Otherwise, VTK recommends using these new webassembly classes instead.

|New class| Old class|
| :----------------: | :------: |
| `vtkWebAssemblyOpenGLRenderWindow`|`vtkSDL2OpenGLRenderWindow`|
| `vtkWebAssemblyWebGPURenderWindow`|`vtkSDL2WebGPURenderWindow`|
| `vtkWebAssemblyRenderWindowInteractor`|`vtkSDL2RenderWindowInteractor`|
