# Supported Data Formats

Below is a list of all available readers and writers in VTK sorted by
extension.  Note that for the same extension it could be more than one matching
reader/writer since the same extensions are often used across different
formats. The list is generated based on a [yaml](./supported_data_formats.yaml)
file that contains all the relevant information.

To enable a reader/writer you need to enable the associated module during configuration:
```
cmake -DVTK_MODULE_ENABLE_<module name>=WANT ...
```
or setting the flag value via `ccmake/cmake-qt`.

For example to enable `vtkPNGWriter` which belongs to {bdg-primary-line}`VTK::IOImage`

```
cmake -DVTK_MODULE_ENABLE_VTK_IOImage=WANT ...
```

For more details on enabling module see the module system [api](api/cmake/ModuleSystem.md#enabling-modules-for-build).

```{warning}
the list is incomplete, this is work in progress
```

{{supported_data_formats_list}}
