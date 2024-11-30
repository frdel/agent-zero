# Building using emscripten for WebAssembly

## Introduction

This page describes how to build and install VTK using [emscripten](https://emscripten.org) on any platform.
These steps can be followed inside a docker container that comes with preinstalled `emsdk` such as
[dockcross/web-wasm](https://hub.docker.com/r/dockcross/web-wasm). In fact, the VTK CI stage `webassembly-build`
uses that container to configure and build VTK wasm.

```{note}

Guide created using

- VTK v9.2.6-2535-gc8cebe56fb
- dockcross/web-wasm:20230222-162287d
```

## Prerequisites

For this guide, you will need the following:

1. **CMake**: [CMake](http://www.cmake.org/) version 3.12 or higher and a
  working compiler. CMake is a tool that makes cross-platform building simple.
  On several systems it will probably be already installed. If it is not,
  please use the following instructions to install it.  There are several
  precompiled binaries available at the [CMake download page](https://cmake.org/download/).
  Add CMake to your PATH environment variable if you downloaded an archive and not an installer.

2. **Emscripten SDK**: [emsdk](https://github.com/emscripten-core/emsdk) and
   any dependencies needed by emsdk.  Emscripten is a complete compiler toolchain
   to WebAssembly, using LLVM, with a special focus on speed, size, and the Web
   platform.  Please download the SDK from
   [github.com/emscripten-core/emsdk.git](https://github.com/emscripten-core/emsdk). Then,

   - Install latest toolchain with `./emsdk install latest`
   - Activate the toolchain `./emsdk activate latest`
   - Run `emsdk_env.bat` or `emsdk_env.ps1` (Windows) or `source ./emsdk_env.sh` (Linux and OS X) to set up the environment for the calling terminal.

   For more detailed instructions see  [emsdk/README.md](https://github.com/emscripten-core/emsdk#readme).

3. **VTK source-code**: If you have these then you can skip the rest of this section and proceed to [Build project](#build-project).
   Download VTK source for the version you want from
   [https://vtk.org/download/](https://vtk.org/download/)  (zip or tar.gz (Do
   NOT download the exe - this is not the VTK library.) ) You will probably
   want the latest one (highest version number) unless you have a specific
   reason to use an older one.

   Alternatively the source-code can be obtained from the repository as well.
   This is recommended only if you intent to make changes and contribute to
   VTK. Please refer to [git/develop.md](../developers_guide/git/develop.md) for help with `git`.

## Build project

These instructions use a specific convention for the source, build and install directories that is appropriate when building VTK for wasm inside
a docker container. Please replace these _root-directory_ paths if VTK is being built outside a docker container.

### Install emscripten ports (IMPORTANT!)

Emscripten relies on SDL2 to link user input events from the browser's event subsystem to native C/C++ code. If this is your initial download of the EMSDK, you'll need to build the SDL2 port. The "embuilder" script will be accessible on the path if you've successfully installed and activated the EMSDK, as outlined in the prerequisites.

```bash
$ embuilder build sdl2
```

### Build VTK

1. Configure the project with CMake. `emcmake` tells CMake to use the `emscripten` toolchain for cross compilation.

```bash
cd /work/src/build
$ emcmake cmake \
  -S .. \
  -B . \
  -G "Ninja" \
  -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_SHARED_LIBS:BOOL=OFF \
  -DVTK_ENABLE_LOGGING:BOOL=OFF \
  -DVTK_ENABLE_WRAPPING:BOOL=OFF \
  -DVTK_MODULE_ENABLE_VTK_RenderingLICOpenGL2:STRING=DONT_WANT
```

2. Compile.

```
$ cd /work/src/build
$ ninja
```

3. Install the project.

```
$ cd /work/src/build
$ ninja install
```

The binaries are now installed and you may use `-DVTK_DIR=/work/install/lib/cmake/vtk-9.2` to configure VTK wasm applications with CMake.

## Verify installation

If everything went well then it should now be possible to compile and run the one of the C++ examples.
Head over to [Examples/Emscripten/Cxx/Cone/README.md](https://gitlab.kitware.com/vtk/vtk/-/blob/master/Examples/Emscripten/Cxx/Cone/README.md)
and test the simple Cone example.

## Multithreading

Multithreading can be enabled in VTK wasm by turning on the CMake setting `VTK_WEBASSEMBLY_THREADS`.
This option simply adds the compile and link flags necessary for emscripten to use WebWorker for a `pthread` and by extension,
`std::thread`. Please refer to [Emscripten/Pthreads](https://emscripten.org/docs/porting/pthreads.html) for details.

You generally want to run your C++ `int main(int, char**)` function in a WebWorker. Doing so keeps the
browser responsive and gives your users a chance to at the very least refresh/close the tab when a long
running VTK algorithm is processing data. You can set this up with the `-sPROXY_TO_PTHREAD=1` linker flag.

If rendering is also part of your main program, please pass `-sPROXY_TO_PTHREAD=1`, `-sOFFSCREENCANVAS_SUPPORT=1`.
These flags will proxy rendering calls to the main browser thread. Since DOM events like mouse, keyboard inputs are
received on the main browser thread, emscripten takes care of queuing the execution of the event callback in the WebWorker
running the VTK application.
You can learn more at [settings_reference/proxy-to-pthread](https://emscripten.org/docs/tools_reference/settings_reference.html#proxy-to-pthread)
and [settings_reference/offscreencanvas-support](https://emscripten.org/docs/tools_reference/settings_reference.html#offscreencanvas-support)

**Tip:**

  If you plan to use a custom DOM `id` for the canvases, please also make sure to pass those as a comma separated list.
  Ex: `-sOFFSCREENCANVASES_TO_PTHREAD=#canvas1,#canvas2`

## 64-bit

*This feature is experimental.*

VTK, by default compiles for the `wasm32-emscripten` architecture. When a 32-bit VTK wasm application
loads and renders very large datasets, it can report out-of-memory errors because the maximum
addressable memory is 4GB. You can overcome this problem by turning on the CMake setting `VTK_WEBASSEMBLY_64_BIT`.
This option compiles VTK for the `wasm64-emscripten` architecture and the maximum addressable memory is 16GB.

In order to execute VTK wasm64 applications, additional flags are required for:
1. chrome/edge: `--js-flags=--experimental-wasm-memory64`.
2. firefox: no flag, use nightly/beta.
3. nodejs: `--experimental-wasm-memory64`.
