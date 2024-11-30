# SPDX & SBOM

## Overview

Software Bill of Materials (SBOM) are becoming increasingly important for
software development, especially when it comes to supply chain security.
[Software Package Data Exchange (SPDX)](https://spdx.dev/) is an open standard
for communicating SBOM information that supports accurate identification of
software components, explicit mapping of relationships between components,
and the association of security and licensing information with each component.

To support this, each VTK module may be described by a `.spdx` file. See [examples](#examples).

Configuring VTK with the option `VTK_GENERATE_SPDX` set to `ON` enables the
[](/api/cmake/ModuleSystem.md#spdx-files-generation) for each VTK module.

:::{caution}
The generation of SPDX files is considered experimental and both the VTK Module system
API and the `SPDXID` used in the generated files may change.
:::

## Frequently Asked Questions

### How to update your module to generate a valid SPDX file ?

In the `vtk.module` file, make sure to specify `SPDX_LICENSE_IDENTIFIER` and `SPDX_COPYRIGHT_TEXT`
as follows:

```
SPDX_LICENSE_IDENTIFIER
  BSD-3-Clause
SPDX_COPYRIGHT_TEXT
  Copyright (c) Ken Martin, Will Schroeder, Bill Lorensen
```

Then add SPDX tags on top of all source files in the module, as follows:

```
// SPDX-FileCopyrightText: Copyright (c) Ken Martin, Will Schroeder, Bill Lorensen
// SPDX-FileCopyrightText: Copyright (c) Awesome contributor
// SPDX-License-Identifier: BSD-3-Clause
```

:::{tip}
Refer to the [limitations](/api/cmake/ModuleSystem.md#limitations) section for more
information on any potential issues that may arise when updating your module to generate
a valid SPDX file.
:::

### How to update a third party to generate a valid SPDX file ?

In the third party `CMakeLists.txt`, make sure to specify, in the `vtk_module_third_party` call,
`SPDX_LICENSE_IDENTIFIER` and `SPDX_COPYRIGHT_TEXT` as follows:

```
 vtk_module_third_party(
    SPDX_LICENSE_IDENTIFIER
      "BSD-3-Clause"
    SPDX_COPYRIGHT_TEXT
      "Copyright (c) Ken Martin, Will Schroeder, Bill Lorensen"
    SPDX_DOWNLOAD_LOCATION
      "git+https://gitlab.kitware.com/third-party/repo.git@hash_or_tag"
    [...]
```

:::{tip}
Refer to the [limitations](/api/cmake/ModuleSystem.md#limitations) section for more
information on any potential issues that may arise when updating your module to generate
a valid SPDX file.
:::

### How to correctly specify custom license for a module ?

In the module, provide a file containing the license.
Then in `vtk.module` file, make sure to specify `SPDX_CUSTOM_LICENSE_FILE` with the path of the license file,
`SPDX_CUSTOM_LICENSE_NAME` with the name of the license and `SPDX_LICENSE_IDENTIFIER`
 with a valid SPDX LicenseRef, as follows:

```
SPDX_LICENSE_IDENTIFIER
  LicenseRef-CustomLicense
SPDX_CUSTOM_LICENSE_FILE
  LICENSE
SPDX_CUSTOM_LICENSE_NAME
  CustomLicense
```

If needed, you can add SPDX tags on top of all source file specifically concerned by this license

```
// SPDX-FileCopyrightText: Copyright (c) Awesome contributor
// SPDX-License-Identifier: LicenseRef-CustomLicense
```

## Examples

This section lists examples of generated SPDX files for different type of VTK modules.

### VTK Module

Example of generated SPDX files for a module in VTK (once the module have been ported to the system):

```
SPDXVersion: SPDX-2.2
DataLicense: CC0-1.0
SPDXID: SPDXRef-DOCUMENT
DocumentName: IOPLY
DocumentNamespace: https://vtk.org/vtkIOPly
Creator: Tool: CMake
Created: 2023-05-16T16:08:29Z

##### Package: IOPLY

PackageName: IOPLY
SPDXID: SPDXRef-Package-IOPLY
PackageDownloadLocation: https://gitlab.kitware.com/vtk/vtk/-/tree/master/IO/PLY
FilesAnalyzed: true
PackageLicenseConcluded: BSD-3-Clause
PackageLicenseDeclared: BSD-3-Clause
PackageLicenseInfoFromFiles: BSD-3-Clause
PackageCopyrightText: <text>
Copyright (c) Ken Martin, Will Schroeder, Bill Lorensen
</text>

Relationship: SPDXRef-DOCUMENT DESCRIBES SPDXRef-Package-IOPLY
```

Example of a SPDX file generated without any information for a module that have not been ported to the system:

```
SPDXVersion: SPDX-2.2
DataLicense: CC0-1.0
SPDXID: SPDXRef-DOCUMENT
DocumentName: vtkFiltersVerdict
DocumentNamespace: https://vtk.org/vtkFiltersVerdict
Creator: Tool: CMake
Created: 2023-05-25T15:16:20Z

##### Package: vtkFiltersVerdict

PackageName: vtkFiltersVerdict
SPDXID: SPDXRef-Package-vtkFiltersVerdict
PackageDownloadLocation: https://gitlab.kitware.com/vtk/vtk/-/tree/master/Filters/Verdict
FilesAnalyzed: false
PackageLicenseConcluded: NOASSERTION
PackageLicenseDeclared: NOASSERTION
PackageLicenseInfoFromFiles: NOASSERTION
PackageCopyrightText: <text>
NOASSERTION
</text>

Relationship: SPDXRef-DOCUMENT DESCRIBES SPDXRef-Package-vtkFiltersVerdict
```

### VTK ThirdParty Module

Example of a complete SPDX file for a 3rd party in VTK (once the 3rd party have been ported to the system):

```
SPDXVersion: SPDX-2.2
DataLicense: CC0-1.0
SPDXID: SPDXRef-DOCUMENT
DocumentName: VTK::loguru
DocumentNamespace: https://vtk.org/vtkloguru
Creator: Tool: CMake
Created: 2023-05-22T15:56:52Z

##### Package: VTK::loguru

PackageName: VTK::loguru
SPDXID: SPDXRef-Package-VTK::loguru
PackageDownloadLocation: https://github.com/Delgan/loguru
FilesAnalyzed: no
PackageLicenseConcluded: BSD-3-Clause
PackageLicenseDeclared: BSD-3-Clause
PackageLicenseInfoFromFiles: NOASSERTION
PackageCopyrightText: <text>
LOGURU Team
</text>

Relationship: SPDXRef-DOCUMENT DESCRIBES SPDXRef-Package-VTK::loguru
```

### VTK Remote Module

Example of a complete SPDX file for a VTK module from outside of VTK (once the module have been ported to the system):

```
SPDXVersion: SPDX-2.2
DataLicense: CC0-1.0
SPDXID: SPDXRef-DOCUMENT
DocumentName: MyModule
DocumentNamespace: https://my-website/MyModule
Creator: Tool: CMake
Created: 2023-05-16T16:08:29Z

##### Package: MyModule

PackageName: MyModule
SPDXID: SPDXRef-Package-MyModule
PackageDownloadLocation: https://github/myorg/mymodule
FilesAnalyzed: true
PackageLicenseConcluded: BSD-3-Clause AND MIT
PackageLicenseDeclared: BSD-3-Clause
PackageLicenseInfoFromFiles: BSD-3-Clause AND MIT
PackageCopyrightText: <text>
Copyright (c) 2023 Popeye
Copyright (c) 2023 Wayne "The Dock" Sonjhon
</text>

Relationship: SPDXRef-DOCUMENT DESCRIBES SPDXRef-Package-MyModule
```

### VTK Module with custom license

Example of a complete SPDX file for a VTK module with a custom license:

```
SPDXVersion: SPDX-2.2
DataLicense: CC0-1.0
SPDXID: SPDXRef-DOCUMENT
DocumentName: IOPLY
DocumentNamespace: https://vtk.org/vtkCustomModule
Creator: Tool: CMake
Created: 2023-05-16T16:08:29Z

##### Package: CustomModule

PackageName: CustomModule
SPDXID: SPDXRef-Package-CustomModule
PackageDownloadLocation: https://gitlab.kitware.com/vtk/vtk/-/tree/master/Custom/Module
FilesAnalyzed: true
PackageLicenseConcluded: BSD-3-Clause
PackageLicenseDeclared: BSD-3-Clause AND LicenseRef-CustomLicense
PackageLicenseInfoFromFiles: BSD-3-Clause
PackageCopyrightText: <text>
Copyright (c) Ken Martin, Will Schroeder, Bill Lorensen
</text>

LicenseID: LicenseRef-CustomLicense
ExtractedText: <text>My License

This is a custom license that is not more restrictive
than BSD license.
</text>

Relationship: SPDXRef-DOCUMENT DESCRIBES SPDXRef-Package-IOPLY
```

## Resources

- https://spdx.dev/
- https://en.wikipedia.org/wiki/Software_supply_chain
- https://www.linuxfoundation.org/blog/blog/spdx-its-already-in-use-for-global-software-bill-of-materials-sbom-and-supply-chain-security
- https://spdx.dev/specifications/
- https://spdx.dev/wp-content/uploads/sites/41/2020/08/SPDX-specification-2-2.pdf
- https://github.com/spdx/spdx-examples
- https://spdx.dev/wp-content/uploads/sites/41/2017/12/spdx_onepager.pdf
