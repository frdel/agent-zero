## vtkVersionQuick-header

* Most of the version macros have been relocated to `vtkVersionQuick.h`. The
  new `VTK_EPOCH_VERSION` macro is defined as the actual `VTK_BUILD_VERSION`
  value for release-track development and a "high" value for future VTK release
  development (i.e., the next minor version bump). The actual build number,
  `VTK_VERSION`, and `VTK_SOURCE_VERSION` values are available in
  `vtkVersionMacros.h`. A new `VTK_VERSION_NUMBER_QUICK` macro provides the VTK
  version as a comparable value with `VTK_VERSION_CHECK` using the
  `VTK_EPOCH_VERSION` instead of `VTK_BUILD_VERSION`. The intent is to reduce
  the rebuild frequency needed for the nightly build version bump for the
  in-development source.
