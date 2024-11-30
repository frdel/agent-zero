## ABI Mangling extention for C/C++ ABI in VTK

Using the C++ feature `inline namespace` VTK is able to apply ABI mangling
to VTK without affecting the API interface in code. This feature allows for
separately compiled VTK libaries isolated in their own translation units to
be linked in the same application without symbol conflicts at runtime.

This feature was "experimental" due to lack of  CI testing and
missing manglings for C ABIs in VTK. Both of these missing components are
now added.

A change from the experimental version to the current version is the splitting
of concerns for the ABI namespace. Previously, `VTK_ABI_NAMESPACE_NAME` allowed
the injection of additional attributes into the namespace such as
`__attribute__ ((visibility (\"hidden\")))`. The `VTK_ABI_NAMESPACE_NAME` is now
guarded to follow a subset of the C++ namespace naming rules (it must match the
regular expression `^[a-zA-Z0-9_]+$`).

* Must contain only lower-case or upper-letters, numbers, or undersores
* Must contain one(1) or more characters.
* Cannot use nested or anonymous namespace names (ie. no `::` or empty names)

Attribute inject is now supported as a separate feature flag `VTK_ABI_NAMESPACE_ATTRIBUTES`
which takes a string of attributes to inject.

Example defining a ABI namespace `vtk9_custom` which applies the `visibility("hidden")`
attribute to all of the VTK bits.

```
cmake -DVTK_ABI_NAMESPACE_NAME=vtk9_custom \
      -DVTK_ABI_NAMESPACE_ATTRIBUTES="__attribute__ ((visibility (\"hidden\")))" \
      $source_path
```

The C ABIs previously skipped by the ABI mangling feature are now included.
Most of the C ABIs have added macros for compatibility in VTK module code.
While the macros allow for use of the unmangled name in code, they do not
allow for loading functions via the DLL interface by the unmangled names.
While the `inline namespace` wrapped mangling allows the injection of extra
attributes, the C ABI mangling currently does not.

Configure warnings were added when configuring features without ABI mangling support
when the `VTK_ABI_NAMESPACE_NAME` is set. While it is still possible to build VTK
with these configurations, it is not recommended.

Notes:
* This change does not affect VTK builds that are not using the `VTK_ABI_NAMESPACE` feature.
* Thirdparty libraries still do not support ABI mangling.
* VTK Wrappings still do not support ABI mangling (ie. Python/Java/etc.).
