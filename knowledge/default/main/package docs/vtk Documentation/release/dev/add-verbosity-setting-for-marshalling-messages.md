# Add new verbsoity setting for log messages related to marshalling

You can now configure the verbsoity level for log messages in the core marshalling classes `vtkDeserializer`, `vtkSerializer` and `vtkObjectManager`. This facilitates debugging (de)serialization
errors in release builds on the desktop and even in wasm.

See the relevant class documentation for detailed information about ways to configure log verbosity.
