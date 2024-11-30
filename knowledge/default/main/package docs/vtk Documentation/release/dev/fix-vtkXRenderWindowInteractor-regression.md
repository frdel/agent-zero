## Fix mainloop restart regression in vtkXRenderWindowInteractor

For the Win32 and Cocoa interactors, the Start() mainloop can be
stopped with TerminateApp() or SetDone(true) and later restarted,
but in VTK 9.2 and 9.3, for the X interactor, calling these methods
would cause the window to close, breaking the X11 display connection.
This behavior has been fixed, allowing the interactor mainloop to be
stopped and restarted with native X11 applications.
