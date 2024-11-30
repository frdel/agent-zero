## Fixed ADIOS2 VTX reader error reporting

The ADIOS2 VTX reader previously reported errors by throwing exceptions.
This causes lots of problems with VTK and programs that use it such as
ParaView because exceptions are not expected. They are not caught or
recovered from. Instead, it just causes applications to crash without
warning. The ADIOS2 VTX reader now properly reports errors by calling
`vtkErrorMacro` and returning 0 from its process request.
