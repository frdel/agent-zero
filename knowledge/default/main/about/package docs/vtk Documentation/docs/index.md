# Modules

```{toctree}
:titlesonly:
:glob:
:hidden:
:caption: Module-specific documentation

./vtk-modules/**
```

VTK library is a dynamic C++ toolkit built around the  concept of "modules". Each module may have dependencies to other VTK module or external libraries.

Foundational dependencies have been wrapped into convenient "module".

## Enabling or Disabling Modules

To enable a module set

```
cmake -DVTK_MODULE_ENABLE_<module name>=WANT ...
```

during the
[configuration](../build_instructions/index.md#configure) stage.

Disabling a module can be done as follows:

```
cmake -DVTK_MODULE_ENABLE_<module name>=DONT_WANT ...
```

Enabling a module may cause more to be enabled due to dependencies.  For more
details about the module infrastructure in VTK see  the
[Module System](../api/cmake/ModuleSystem.md) section.

## Available Modules

Here is a complete list of the available vtk modules:

{{ module_table }}
