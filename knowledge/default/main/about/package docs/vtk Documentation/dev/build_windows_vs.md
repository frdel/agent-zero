# Building VTK using Visual Studio on Windows

## Introduction

This page describes how to build and install VTK using Visual Studio on Windows in recipe-style fashion. It is also possible to build VTK on Windows without using Visual Studio directly, this is covered in [Building VTK](build.md).

Adapted from the [Paraview build instructions](https://gitlab.kitware.com/paraview/paraview/-/blob/master/Documentation/dev/build.md) and [VTK wiki](https://vtk.org/Wiki/VTK/Building/Windows).
Inspired by [This video](https://www.youtube.com/watch?v=IgvbhyDh8r0)

## Prerequisites

For this guide you will need to following:

1. CMake [CMake](http://www.cmake.org/) version 3.10 or higher and a working compiler.
2. Visual Studio with C++ support
3. The VTK Source-code

If you have these then you can skip the rest of this section and proceed to BUILD SOLUTION.

### Get CMake

CMake is a tool that makes cross-platform building simple. On several systems it will probably be already installed. If it is not, please use the following instructions to install it.
There are several precompiled binaries available at the [CMake download page](https://cmake.org/download/). Download version 3.10 or later.
Add CMake to your PATH environment variable if you downloaded an archive and not an installer.

This guide was tested using cmake 3.13.4 64bit installed by downloading the .msi installer. [cmake-3.13.4-win64-x64.msi]

### Get Visual Studio

This guide uses Visual Studio / C++ as IDE and compiler. Visual studio can be installed from [Download](https://visualstudio.microsoft.com/vs/community/).
This howto uses the free community edition.
During installation select the "desktop development with C++" workload.

### Get VTK Source-code

Download VTK source for the version you want from [https://vtk.org/download/](https://vtk.org/download/)  (zip or tar.gz (Do NOT download the exe - this is not the VTK library.) )
You will probably want the latest one (highest version number) unless you have a specific reason to use an older one.

Alternatively the source-code can be obtained from the repository as well. This is recommended only if you intent to make changes and contribute to VTK.

## BUILD SOLUTION

Use CMake to create a solution that visual studio can open.

### Prepare folder structure

1. Create a folder for VTK.
2. In this folder, create two subfolders; "src" and "build"
3. Extract the contents of the VTK folder in the downloaded archive to the subfolder called src

You should now have something like:

``` cmd
c:\data\cpp\vtk\build    <--empty
c:\data\cpp\vtk\src
c:\data\cpp\vtk\src\Accelerators
c:\data\cpp\vtk\src\Charts
c:\data\cpp\vtk\src\....
```

### Run CMake

Use CMake to generate a visual studio solution.

1. Open CMake-GUI, either by typing cmake-gui on the command prompt or from the start-menu.
2. Enter the source and build directories

   ![cmake1](images/cmake1.png)

3. Click [Configure]
4. You will now get a selection screen in which you can specify your "generator". Select the one you need. This guide was tested with Visual Studio 15 2017 Win64 in combination with the default options.

   This will take some time. You may want to spend this time useful by reading [cmake overview](https://cmake.org/overview/) and [cmake example](https://cmake.org/examples) and even the [cmake tutorial](https://cmake.org/cmake-tutorial/).

5. We are now presented with a few options that can be turned on or off as desired. For this guide the only change made is to
   - Check the box after CMAKE_CXX_MP_FLAG. This enables building using multi-core.
6. Click [Configure] to apply the changes.
7. Click [Generate]. This will populate the "build" sub-folder.
8. Finally, click [Open Project] to open the generated solution in Visual Studio.

### Build

Use Visual Studio to build the .dll files.
The last step of CMake will launch Visual Studio and will open the generated solution.

1. Set the configuration to "Release"
2. Build the "ALL_BUILD" project.

Again, this will take a while [About ten minutes on a 2-core i7].

After this there should be a folder /build/bin/Release containing the created .dll libraries.

## INSTALL

To be able to use VTK in other project it first needs to be installed.

1. Start CMake-gui (again)
2. As source-code dir enter the src folder (again).
3. Hit [Configure]
4. Set the "CMKAE_INSTALL_PREFIX" directory.

   ![cmake4](images/cmake4.png)

5. Click [Generate]
6. Click [Open Project]

   In Visual Studio

   1. Build the "ALL_BUILD" project again. Should be very quick this time.
   2. Build the "INSTALL" project.

   At this moment Visual Studio may FAIL because it is not allowed to create the installation folder.

   ![adminerror1](images/adminerror1.png)

   If this happens then you have two options:

   - Either repeat the previous steps with a different install directory in CMAKE
   - Start Visual Studio as administrator by right-clicking on its icon and selecting "start as administrator". ![vs4](images/vs4.png)

   After installation where VTK should have been installed in the specified installation directory. Something like the following directories should now exist:

   ``` cmd
   c:\program file\VTK\bin
   c:\program file\VTK\include
   c:\program file\VTK\lib
   c:\program file\VTK\share
   ```

   The /bin folder contains all the .dll files that are needed to run an application using VTK. In order to be able to find these files it needs to be added to the path environment variable.

7. Add the folder /bin folder to the windows path. [start -> Edit the system environment variables -> Advanced -> Environment Variables -> Path -> Edit -> New]

## TEST WITH AN EXAMPLE

If everything went well then it should now be possible to compile and run the one of the C++ examples.

From [vtk-examples](https://kitware.github.io/vtk-examples/site/Cxx/) pick a simple but appealing one. In this guide we've used [this one](https://kitware.github.io/vtk-examples/site/Cxx/Picking/HighlightPickedActor/)

1. Downloads or copy-paste the .cxx and CMakeLists.txt files and save them in the same folder.
2. Open CMake and select the folder where the files were saves as "where is the source code" folder.
3. Click [Configure]
4. Verify that the VTK_DIR is set correctly. This folder should contain the file UseVTK.cmake

   ![cmake5](images/cmake5.png)

5. Click [Configure]
6. Click [Generate]

   If you get an error then make sure that the file-names specified in CMakeLists.txt match the source file. Visual studio used .cpp as extension for C++ files while the cmake files contain references to .cxx

7. Click [Open Project]

   In visual studio:

   1. Select the example (HighlightPickedActor) as start-up project. (right click -> set as start-up project)
   2. Run!

![TestHighlightPickedActor](images/TestHighlightPickedActor.png)

If your program complains about missing DLLs then check if the .dll path (last step of INSTALL section) was added correctly.

## Guide created using

- VTK 8.2.0
- CMake 3.13.4
- Visual Studio 2017 ; community edition
- x64
- Windows 10
