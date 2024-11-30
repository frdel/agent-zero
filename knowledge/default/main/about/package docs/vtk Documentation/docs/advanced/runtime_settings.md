# Runtime settings

## OpenGL

On Linux and Windows, VTK will attempt to detect support for an OpenGL context backend at runtime
and create an appropriate subclass of `vtkOpenGLRenderWindow`. You can override this process by
specifying an environment variable `VTK_DEFAULT_OPENGL_WINDOW`. The possible values
are:

  1. `vtkXOpenGLRenderWindow` (Linux; applicable only when `VTK_USE_X` is `ON`, which is the default setting)
  2. `vtkWin32OpenGLRenderWindow` (Windows; applicable only when `VTK_USE_WIN32_OPENGL` is `ON`, which is the default setting)
  3. `vtkEGLRenderWindow` (applicable only when `VTK_OPENGL_HAS_EGL` is `ON`, which is the default setting)
  4. `vtkOSOpenGLRenderWindow` (OSMesa, requires that `osmesa.dll` or `libOSMesa.so` is installed)

Note: VTK does **not** support OSMesa on macOS, iOS, Android and WebAssembly platforms.

### Multisample anti-aliasing

Some OpenGL drivers have rendering problems when Multisample anti-aliasing is enabled.
It is possible to specify the environment variable `VTK_FORCE_MSAA` to troubleshoot rendering problems with these values:

  1. `0` to disable MSAA
  2. `1` to enable it regardless even when the driver is known to have problems with MSAA
