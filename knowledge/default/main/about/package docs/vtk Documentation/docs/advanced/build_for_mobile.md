# Cross-compiling for Mobile devices

```{tip}
For complete build instructions see [here](../build_instructions/build.md).
```

VTK supports mobile devices in its build. These are triggered by a top-level
flag which then exposes some settings for a cross-compiled VTK that is
controlled from the top-level build.

iOS builds may be enabled by setting the `VTK_IOS_BUILD` option. The following
settings than affect the iOS build:

  * `IOS_SIMULATOR_ARCHITECTURES`
  * `IOS_DEVICE_ARCHITECTURES`
  * `IOS_DEPLOYMENT_TARGET`
  * `IOS_EMBED_BITCODE`

Android builds may be enabled by setting the `VTK_ANDROID_BUILD` option. The
following settings affect the Android build:

  * `ANDROID_NDK`
  * `ANDROID_NATIVE_API_LEVEL`
  * `ANDROID_ARCH_ABI`
