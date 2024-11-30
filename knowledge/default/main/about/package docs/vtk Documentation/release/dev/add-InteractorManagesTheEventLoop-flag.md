# New flag vtkRenderWindowInteractor::InteractorManagesTheEventLoop for event loop

This flag is useful when you are integrating VTK in a larger system.
In such cases, an application can lock up if the `Start()` method
in vtkRenderWindowInteractor processes events indefinitely without
giving the system a chance to execute anything.
The default value for this flag is true. It currently only affects
VTK webassembly applications.

As an example with webassembly in the browser through emscripten SDK:

1. If your app has an `int main` entry point, leave this value enabled.
   Emscripten will simulate an infinite event loop and avoid running code
   after `interactor->Start()` which is usually the end of `main`.
   Otherwise, all VTK objects will go out of scope immediately without
   giving a chance for user interaction with the render window.
2. If your app does not have an `int main` entry point, disable this
   behavior.
   Otherwise, the webassembly application will not start up successfully.
