# Build Settings

VTK has a number of settings available for its build. The common variables
to modify include:

  * `BUILD_SHARED_LIBS` (default `ON`): If set, shared libraries will be
    built. This is usually what is wanted.
  * `VTK_USE_CUDA` (default `OFF`): Whether [CUDA][cuda] support will be available or
    not.
  * `VTK_USE_MPI` (default `OFF`): Whether [MPI][mpi] support will be available or
    not.
  * `VTK_WRAP_PYTHON` (default `OFF`; requires `VTK_ENABLE_WRAPPING`): Whether
    Python support will be available or not.

Less common, but variables which may be of interest to some:

  * `VTK_BUILD_EXAMPLES` (default `OFF`): If set, VTK's example code will be
    added as tests to the VTK test suite.
  * `VTK_ENABLE_LOGGING` (default `ON`): If set, enhanced logging will be
    enabled.
  * `VTK_LOGGING_TIME_PRECISION` (default `3`; requires `VTK_ENABLE_LOGGING`):
    Change the precision of times output when `VTK_ENABLE_LOGGING` is on.
  * `VTK_BUILD_TESTING` (default `OFF`): Whether to build tests or not. Valid
    values are `OFF` (no testing), `WANT` (enable tests as possible), and `ON`
    (enable all tests; may error out if features otherwise disabled are
    required by test code).
  * `VTK_ENABLE_KITS` (default `OFF`; requires `BUILD_SHARED_LIBS`): Compile
    VTK into a smaller set of libraries. Can be useful on platforms where VTK
    takes a long time to launch due to expensive disk access.
  * `VTK_ENABLE_WRAPPING` (default `ON`): Whether any wrapping support will be
    available or not.
  * `VTK_WRAP_JAVA` (default `OFF`; requires `VTK_ENABLE_WRAPPING`):
    Whether Java support will be available or not.
  * `VTK_WRAP_SERIALIZATION` (default `OFF`; requires `VTK_ENABLE_WRAPPING`):
    Whether serialization code will be auto generated or not.
  * `VTK_JAVA_INSTALL` (default `OFF`; requires `VTK_WRAP_JAVA`):
    Whether to build the Java Maven package for VTK.
  * `VTK_SMP_IMPLEMENTATION_TYPE` (default `Sequential`): Set which SMPTools
    will be implemented by default. Must be either `Sequential`, `STDThread`,
    `OpenMP` or `TBB`. The backend can be changed at runtime if the desired
    backend has his option `VTK_SMP_ENABLE_<backend_name>` set to `ON`.
  * `VTK_ENABLE_CATALYST` (default `OFF`): Enable catalyst-dependent modules
    including the VTK catalyst implementation. Depends on an external Catalyst.
  * `VTK_WEBASSEMBLY_64_BIT` (default `OFF`):
    This option is applicable only when building with Emscripten toolchain.
    Adds -sMEMORY64 compiler and linker flags.
  * `VTK_WEBASSEMBLY_THREADS` (default `OFF`):
    This option is applicable only when building with Emscripten toolchain.
    Adds -pthread compiler and linker flags. When `VTK_BUILD_TESTING` is `ON`,
    this also runs unit tests in web workers, which is the only way for the tests
    to reliably load data files without having to embed entire datasets inside
    the test binaries.
  * `VTK_TESTING_WASM_ENGINE` (default ``):
    Path to a wasm runtime executable. This is used to run C++ tests in wasm environments.

## OpenGL related build options:

When OpenGL is used, a valid rendering environment (e.g., X, Cocoa, SDL2, OSMesa, EGL) must be available.
Sanity checks are in place to prevent a broken build.

For specific platforms:
* Android: `vtkEGLRenderWindow` is the default.
* macOS: `vtkCocoaRenderWindow` is the default.
* iOS: `vtkIOSRenderWindow` is the default.
* WebAssembly: `vtkWebAssemblyOpenGLRenderWindow` is the default.

Please learn more about how you can influence the render window selection process in [](/advanced/runtime_settings.md#opengl)

## Additional Rendering related build options:
On Linux, the order of render window attempts is:

1. `vtkXOpenGLRenderWindow`
2. `vtkEGLRenderWindow`
3. `vtkOSOpenGLRenderWindow`

On Windows:

* `vtkWin32OpenGLRenderWindow`
* `vtkOSOpenGLRenderWindow`

By default, VTK automatically selects the most appropriate render window class at runtime. This selection process uses the `Initialize` method of the compiled subclass to test whether the chosen setup is valid. If the initialization succeeds, the corresponding render window instance is returned.

The default values of the following CMake `VTK_OPENGL_HAS_*` knobs are already configured so
that the above condition is always met on all supported platforms.

  * `VTK_USE_COCOA` (default `ON`; requires macOS): Use Cocoa for
    render windows.
  * `VTK_USE_X` (default `ON` for Unix-like platforms except macOS,
    iOS, and Emscripten, `OFF` otherwise): Use X for render windows.
  * `VTK_USE_SDL2` (default `OFF`): Use SDL2 for render windows.
  * `VTK_OPENGL_USE_GLES` (default `OFF`; forced `ON` for Android):
    Whether to use OpenGL ES API for OpenGL or not.
  * `VTK_OPENGL_HAS_EGL` (default `ON` for Android and Linux, `OFF` otherwise):
    Use to indicate that the OpenGL library being used supports EGL
    context management.
  * `VTK_DEFAULT_EGL_DEVICE_INDEX` (default `0`; requires
    `VTK_OPENGL_HAS_EGL`): The default EGL device to use for EGL render
    windows.
  * `VTK_ENABLE_WEBGPU` (default `OFF`; required if using Emscripten): Enable
    WebGPU rendering support.
  * `VTK_DEFAULT_RENDER_WINDOW_OFFSCREEN` (default `OFF`): Whether to default
    to offscreen render windows by default or not.
  * `VTK_USE_OPENGL_DELAYED_LOAD` (default `OFF`; requires Windows and CMake >=
    3.13): If set, use delayed loading to load the OpenGL DLL at runtime.
  * `VTK_DEFAULT_RENDER_WINDOW_HEADLESS` (default `OFF`; only available if
    applicable): Default to a headless render window.
  * `VTK_USE_WIN32_OPENGL` (default `ON` for Windows, forced `OFF` otherwise):
    Use Win32 APIs for render windows (typically only relevant for OSMesa on
    Windows builds).

More advanced options:

  * `VTK_ABI_NAMESPACE_NAME` (default `<DEFAULT>` aka `""`): If set, VTK will
     wrap all VTK public symbols in an
     `inline namespace <VTK_ABI_NAMESPACE_NAME>` to allow runtime co-habitation
     with different VTK versions.
     Some C ABIs are also wrapped in this namespace using macro expansion
     `#define c_abi VTK_ABI_NAMESPACE_MANGLE(c_abi)`
  * `VTK_ABI_NAMESPACE_ATTRIBUTES` (default `<DEFAULT>` aka `""`): If set, VTK will
     inject these attributes into the `inline namespace`. i.e.
     `inline namespace <VTK_ABI_NAMESPACE_ATTRIBUTES> <VTK_ABI_NAMESPACE_NAME>`
     The `VTK_ABI_NAMESPACE_ATTRIBUTES` is only applied the the APIs inside of the
     namespace, not to C APIs.
  * `VTK_BUILD_DOCUMENTATION` (default `OFF`): If set, VTK will build its API
    documentation using Doxygen.
  * `VTK_BUILD_SPHINX_DOCUMENTATION` (default `OFF`): If set, VTK will build its sphinx
    documentation website.
  * `VTK_BUILD_ALL_MODULES` (default `OFF`): If set, VTK will enable all
    modules not disabled by other features.
  * `VTK_ENABLE_REMOTE_MODULES` (default `ON`): If set, VTK will try to build
    remote modules (the `Remote` directory). If unset, no remote modules will
    build.
  * `VTK_ENABLE_EXTRA_BUILD_WARNINGS` (default `OFF`; requires CMake >= 3.19):
    If set, VTK will enable additional build warnings.
  * `VTK_ENABLE_EXTRA_BUILD_WARNINGS_EVERYTHING` (default `OFF`; requires
    `VTK_ENABLE_EXTRA_BUILD_WARNINGS` and `-Weverything` support): If set, VTK
    will enable all build warnings (with some explicitly turned off).
  * `VTK_USE_EXTERNAL` (default `OFF`): Whether to prefer external third
    party libraries or the versions VTK's source contains.
  * `VTK_TARGET_SPECIFIC_COMPONENTS` (default `OFF`): Whether to install
    files into target-specific components (`<TARGET>-runtime`,
    `<TARGET>-development`, etc.) or general components (`runtime`,
    `development`, etc.)
  * `VTK_VERSIONED_INSTALL` (default `ON`): Whether to add version numbers to
    VTK's include directories and library names in the install tree.
  * `VTK_CUSTOM_LIBRARY_SUFFIX` (default depends on `VTK_VERSIONED_INSTALL`):
    The custom suffix for libraries built by VTK. Defaults to either an empty
    string or `X.Y` where `X` and `Y` are VTK's major and minor version
    components, respectively.
  * `VTK_CUSTOM_LIBRARY_VERSION` (default depends on `VTK_VERSIONED_INSTALL`):
    The custom version for libraries built by VTK. Defaults to either an empty
    string  or `X.Y` where `X` and `Y` are VTK's major and minor version if
    VTK_VERSIONED_INSTALL is ON.
  * `VTK_INSTALL_SDK` (default `ON`): If set, VTK will install its headers,
    CMake API, etc. into its install tree for use.
  * `VTK_FORBID_DOWNLOADS` (default `OFF`): If set, VTK will error on any
    network activity required during the build (namely remote modules and
    testing data).
  * `VTK_DATA_STORE` (default is complicated): If set or detected, points to
    where VTK external data will be stored or looked up.
  * `VTK_DATA_EXCLUDE_FROM_ALL` (default is complicated, but
    generally `OFF`): If set or detected, data downloads will only
    happen upon explicit request rather than through the build's
    default target.
  * `VTK_RELOCATABLE_INSTALL` (default `ON`): If set, the install tree will be
    relocatable to another path. If unset, the install tree may be tied to the
    build machine with absolute paths, but finding dependencies in
    non-standard locations may require work without passing extra information
    when consuming VTK.
  * `VTK_UNIFIED_INSTALL_TREE` (default `OFF`): If set, the install tree is
    stipulated to be a unified install tree of VTK and all of its dependencies;
    a unified tree usually simplifies things including, but not limited to,
    the Python module paths, library search paths, and plugin searching. This
    option is irrelevant if a relocatable install is requested as such setups
    assume that dependencies are set up either via a unified tree or some other
    mechanism such as modules).
  * `VTK_ENABLE_SANITIZER` (default `OFF`): Whether to enable sanitization of
    the VTK codebase or not.
  * `VTK_SANITIZER` (default `address`; requires `VTK_ENABLE_SANITIZER`): The
    sanitizer to use.
  * `VTK_USE_LARGE_DATA` (default `OFF`; requires `VTK_BUILD_TESTING`):
    Whether to enable tests which use "large" data or not (usually used to
    reduce the amount of data downloading required for the test suite).
  * `VTK_USE_HIP` (default `OFF`; requires CMAKE >= 3.21 and NOT `VTK_USE_CUDA`)
    Whether [HIP][hip] support will be available or not.
  * `VTK_LEGACY_REMOVE` (default `OFF`): If set, VTK will disable legacy,
    deprecated APIs.
  * `VTK_LEGACY_SILENT` (default `OFF`; requires `VTK_LEGACY_REMOVE` to be
    `OFF`): If set, usage of legacy, deprecated APIs will not cause warnings.
  * `VTK_USE_FUTURE_CONST` (default `OFF`): If set, the `VTK_FUTURE_CONST`
    macro expands to `const`; otherwise it expands to nothing. This is used to
    incrementally add more const correctness to the codebase while making it
    opt-in for backwards compatibility.
  * `VTK_USE_FUTURE_BOOL` (default `OFF`): If set, the `vtkTypeBool`
    typedef is defined to `bool`; otherwise it's `int`. VTK was created before
    C++ even had `bool`, and so its oldest code used `int`. Set to `ON` to opt in
    to using more real `bool`s, set to `OFF` only if required for backwards
    compatibility.
  * `VTK_USE_TK` (default `OFF`; requires `VTK_WRAP_PYTHON`): If set, VTK will
    enable Tkinter support for VTK widgets.
  * `VTK_BUILD_COMPILE_TOOLS_ONLY` (default `OFF`): If set, VTK will compile
    just its compile tools for use in a cross-compile build.
  * `VTK_NO_PYTHON_THREADS` (default `OFF`): If set, then all Python threading
    in VTK will be disabled.
  * `VTK_PYTHON_FULL_THREADSAFE` (default `ON`): If set, lock the Python GIL
    for Python C API calls, to make it safe to allow Python thread concurrency.
  * `VTK_SERIAL_TESTS_USE_MPIEXEC` (default `OFF`): Used on HPC to run
    serial tests on compute nodes. If set, it prefixes serial tests with
    "${MPIEXEC_EXECUTABLE}" "${MPIEXEC_NUMPROC_FLAG}" "1" ${MPIEXEC_PREFLAGS}
  * `VTK_WINDOWS_PYTHON_DEBUGGABLE` (default `OFF`): Set to `ON` if using a
    debug build of Python.
  * `VTK_WINDOWS_PYTHON_DEBUGGABLE_REPLACE_SUFFIX` (default `OFF`): Set to `ON`
    to use just a `_d` suffix for Python modules.
  * `VTK_BUILD_PYI_FILES` (default `OFF`): Set to `ON` to build `.pyi` type
    hint files for VTK's Python interfaces.
  * `VTK_DLL_PATHS` (default `""` or `VTK_DLL_PATHS` from the environment): If
    set, these paths will be added via Python 3.8's `os.add_dll_directory`
    mechanism in order to find dependent DLLs when loading VTK's Python
    modules. Note that when using the variable, paths are in CMake form (using
    `/`) and in the environment are a path list in the platform's preferred
    format.
  * `VTK_ENABLE_VR_COLLABORATION` (default `OFF`): If `ON`, includes support
    for multi client VR collaboration. Requires libzmq and cppzmq external libraries.
  * `VTK_SMP_ENABLE_<backend_name>` (default `OFF` if needs an external library otherwise `ON`):
    If set, builds with the specified SMPTools backend implementation that can be
    changed on runtime with `VTK_SMP_BACKEND_IN_USE` environment variable.
  * `VTK_USE_VIDEO_FOR_WINDOWS` (default `OFF`; requires Windows): Enable the
    `vtkAVIWriter` class in the `VTK::IOMovie` module.
  * `VTK_USE_VIDEO_FOR_WINDOWS_CAPTURE` (default `OFF`; requires Windows):
    Enable the `vtkWin32VideoSource` class in the `VTK::IOVideo` module.
  * `VTK_USE_MICROSOFT_MEDIA_FOUNDATION` (default `OFF`; requires Windows):
    Enable the `vtkMP4Writer` class in the `VTK::IOMovie` module.
  * `VTK_USE_64BIT_TIMESTAMPS` (default `OFF`; forced on for 64-bit builds):
    Build with 64-bit `vtkMTimeType`.
  * `VTK_USE_64BIT_IDS` (default `OFF` for 32-bit builds; `ON` for 64-bit
    builds): Whether `vtkIdType` should be 32-bit or 64-bit.
  * `VTK_DEBUG_LEAKS` (default `OFF`): Whether VTK will report leaked
    `vtkObject` instances at process destruction or not.
  * `VTK_DEBUG_RANGE_ITERATORS` (default `OFF`; requires a `Debug` build):
    Detect errors with `for-range` iterators in VTK (note that this is very
    slow).
  * `VTK_ALWAYS_OPTIMIZE_ARRAY_ITERATORS` (default `OFF`; requires `NOT
    VTK_DEBUG_RANGE_ITERATORS`): Optimize `for-range` array iterators even in
    `Debug` builds.
  * `VTK_ALL_NEW_OBJECT_FACTORY` (default `OFF`): If `ON`, classes using
    `vtkStandardNewMacro` will use `vtkObjectFactoryNewMacro` allowing
    overrides to be available even when not explicitly requested through
    `vtkObjectFactoryNewMacro` or `vtkAbstractObjectFactoryNewMacro`.
  * `VTK_ENABLE_VTKM_OVERRIDES` (default `OFF`): If `ON`, enables factory override
     of certain VTK filters by their VTK-m counterparts. There is also a runtime
     switch that can be used to enable/disable the overrides at run-time (on by default).
     It can be accessed using the static function `vtkmFilterOverrides::SetEnabled(bool)`.
  * `VTK_GENERATE_SPDX` (default `OFF`): If `ON`, SPDX file will be generated at build time
     and installed for each module and third party, in order to be able to create a SBOM.
     See [](/api/cmake/ModuleSystem.md#spdx-files-generation) and
     [](/advanced/spdx_and_sbom.md) for more info.
  * `VTK_ANARI_ENABLE_NVTX` (default `OFF`; requires CUDA Toolkit): If `ON`, enables the NVIDIA
     Tools Extension Library (NVTX) for profiling the ANARI rendering code and visualizing
     these events in tools like [NSight Systems][nsight].

`vtkArrayDispatch` related options:

The `VTK_DISPATCH_<array_type>_ARRAYS` options (default `OFF` for all but AOS) enable the
specified type of array to be included in a dispatch type list. Explicit arrays (such as
AOS, SOA, Typed, and implicit arrays) are included in the `vtkArrayDispatchTypeList.h`
The implicit array framework is included in the `CommonCore` module. The following array types
currently exist for use with the VTK dispatch mechanism:

  * `VTK_DISPATCH_AOS_ARRAYS` (default `ON`): includes dispatching for the commonly used
    "array-of-structure" ordered arrays derived from `vtkAOSDataArrayTemplate`
  * `VTK_DISPATCH_SOA_ARRAYS` (default `OFF`): includes dispatching for "structure-of-array"
    ordered arrays derived from `vtkSOADataArrayTemplate`
  * `VTK_DISPATCH_TYPED_ARRAYS` (default `OFF`): includes dispatching for arrays derived
    from `vtkTypedDataArray`
  * `VTK_DISPATCH_AFFINE_ARRAYS` (default `OFF`): includes dispatching for linearly varying
    `vtkAffineArray`s as part of the implicit array framework
  * `VTK_DISPATCH_CONSTANT_ARRAYS` (default `OFF`): includes dispatching for constant arrays
    `vtkConstantArray` as part of the implicit array framework
  * `VTK_DISPATCH_STD_FUNCTION_ARRAYS` (default `OFF`): includes dispatching for arrays with
    an `std::function` backend `vtkStdFunctionArray` as part of the implicit array framework

The outlier in terms of dispatch support is the family of arrays derived from
`vtkScaledSOADataArrayTemplate` which are automatically included in dispatch when built setting
the `VTK_BUILD_SCALED_SOA_ARRAYS`.

```{warning}
Adding increasing numbers of arrays in the dispatch mechanism can greatly slow down compile times.
```

The VTK module system provides a number of variables to control modules which
are not otherwise controlled by the other options provided.

  * `VTK_MODULE_USE_EXTERNAL_<name>` (default depends on `VTK_USE_EXTERNAL`):
    Use an external source for the named third-party module rather than the
    copy contained within the VTK source tree.

     ````{warning}
       Activating this option within an interactive cmake configuration (i.e. ccmake, cmake-gui)
       could end up finding libraries in the standard locations rather than copies
       in non-standard locations.

       It is recommended to pass the variables necessary to find the intended external package to
       the first configure to avoid finding unintended copies of the external package.
       The variables which matter depend on the package being found, but those ending with
       `_LIBRARY` and `_INCLUDE_DIR` as well as the general CMake `find_package` variables ending
       with `_DIR` and `_ROOT` are likely candidates.

       Example:
       ```
       ccmake -D HDF5_ROOT:PATH=/home/user/myhdf5 ../vtk/sources
       ```
     ````

  * `VTK_MODULE_ENABLE_<name>` (default `DEFAULT`): Change the build settings
    for the named module. Valid values are those for the module system's build
    settings (see below).
  * `VTK_GROUP_ENABLE_<name>` (default `DEFAULT`): Change the default build
    settings for modules belonging to the named group. Valid values are those
    for the module system's build settings (see below).

For variables which use the module system's build settings, the valid values are as follows:

  * `YES`: Require the module to be built.
  * `WANT`: Build the module if possible.
  * `DEFAULT`: Use the settings by the module's groups and
    `VTK_BUILD_ALL_MODULES`.
  * `DONT_WANT`: Don't build the module unless required as a dependency.
  * `NO`: Do not build the module.

If any `YES` module requires a `NO` module, an error is raised.

[cuda]: https://developer.nvidia.com/cuda-zone
[hip]: https://en.wikipedia.org/wiki/ROCm
[mpi]: https://www.mcs.anl.gov/research/projects/mpi
[nsight]: https://developer.nvidia.com/nsight-systems
