## Add VTK::catalyst module

VTK now has a new module called `VTK::catalyst` which is enabled with VTK_ENABLE_CATALYST,
It looks for an external Catalyst installation and exposes catalyst's CMake functionality.
Other VTK modules, such as `VTK::IOCatalystConduit`, can now depend on `VTK::catalyst` instead
of trying to find the Catalyst package themselves.
