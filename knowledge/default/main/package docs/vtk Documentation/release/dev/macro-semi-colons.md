## Some function-like macros now require trailing semi-colons

Function-like macros such as vtkVLog, vtkLog, vtkVLogIf, vtkLogIf, vtkOpenGLCheckErrorMacro, vtkOpenGLStaticCheckErrorMacro, and vtkOpenGLDebugCheckErrorMacro (and perhaps more, that are implemented using them), now require a trailing semi-colon where invoked.  For example, this would have previously compiled:

```c++
vtkLog(ERROR, "No output data.")
```

but now *must* be written as:

```c++
vtkLog(ERROR, "No output data.");
```

Adding the semi-colon will result in code that compiles both before and after this change, and so your code can still be compatible with old and new VTK.

This change was motivated by making the VTK codebase compile cleanly with the clang `-Wextra-semi-stmt` warning.
