## ANARI Rendering Module

You can now use [ANARI](https://www.khronos.org/anari), by enabling the `vtkRenderingANARI` module, for rendering. At least one [ANARI](https://www.khronos.org/anari) back-end needs to be in your `LIBRARY_PATH` and the `ANARI_LIBRARY` environment variable needs to be set with the correct back-end name (e.g. `export ANARI_LIBRARY=visrtx`).

Any back-end compatible with **ANARI-SDK version 0.9.1** will work. [NVIDIA VisRTX](https://github.com/NVIDIA/VisRTX) version 0.7.1 has been tested and is compatible with this release.

Here's the list of other publicly available back-ends:

* [AMD RadeonProRender](https://github.com/GPUOpen-LibrariesAndSDKs/RadeonProRenderANARI)
* [Intel OSPRay](https://github.com/ospray/anari-ospray)
* [NVIDIA USD](https://github.com/NVIDIA-Omniverse/AnariUsdDevice)

> :warning: Before using any back-end, check that the version is compatible with **ANARI-SDK version 0.9.1**.
