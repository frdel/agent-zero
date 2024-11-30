# Resources

For commercial or confidential consulting related to VTK or any of our other products and services, please contact [Kitware’s advanced support team](https://www.kitware.com/contact/advanced-support/) for personalized assistance.

## Links

| Name     | Description                                           |               |
|----------|-------------------------------------------------------|-----------------|
| Book     | Descriptions of important visualization algorithms, including example images and code that utilizes VTK | book.vtk.org|
| Discourse| Community forum                                           | discourse.vtk.org |
| GitLab   | Merge requests and issues take place here                 | gitlab.kitware.com/vtk/vtk |
| Examples | Examples, Tutorials, and guides for VTK in C++ and Python | examples.vtk.org |
| Doxygen  | Documentation of VTK C++ classes updated daily            | vtk.org/doc/nightly/html |
| CDash    | Quality Dashboard                                         | open.cdash.org/index.php?project=VTK |


## Python

| Name     | Description                                           |                   |
|----------|-------------------------------------------------------|-------------------|
| PyPI     | Python Wheels                                         | `pip install vtk` |
| `wheels.vtk.org`  | See [](./advanced/available_python_wheels.md)  | `pip install --extra-index-url https://wheels.vtk.org vtk` |

## Docker

The VTK Docker Repositories are a set of ready-to-run [Docker images](https://hub.docker.com/search?q=kitware%2Fvtk) aiming to support development and testing of VTK-based projects.

| Repository | Description | `Dockerfile` |
|------------|-------------|--------------|
| [`kitware/vtk`][dockerhub-vtk] | Images with built dependencies to support the continuous integration of VTK | [{material-regular}`code;2em`][dockerfile-vtk] |
| [`kitware/vtk-for-ci`][dockerhub-vtk-for-ci] | Images with installation of VTK (in `/opt/vtk/install`) to support building & testing your VTK-based projects. <br/>Learn more reading [this blog](https://www.kitware.com/adding-ci-to-your-paraview-plugin-and-vtk-modules/). | |
| [`kitware/vtk-wasm`][dockerhub-vtk-wasm] | Static emscripten build of VTK to support building VTK-based WebAssembly applications. See [](getting_started/using_webassembly.md) |[{material-regular}`code;2em`][dockerfile-vtk-wasm] |
| [`kitware/vtkm`][dockerhub-vtkm] | Images with built dependencies to support the continuous integration of [VTK-m][vtk-m]. | [{material-regular}`code;2em`][dockerfile-vtkm] |

[dockerhub-vtk]: https://hub.docker.com/r/kitware/vtk
[dockerfile-vtk]: https://gitlab.kitware.com/vtk/vtk/-/tree/master/.gitlab/ci/docker

[dockerhub-vtk-for-ci]: https://hub.docker.com/r/kitware/vtk-for-ci

[dockerhub-vtk-wasm]: https://hub.docker.com/r/kitware/vtk-wasm
[dockerfile-vtk-wasm]: https://gitlab.kitware.com/vtk/vtk-wasm-docker

[dockerhub-vtkm]: https://hub.docker.com/r/kitware/vtkm
[dockerfile-vtkm]: https://gitlab.kitware.com/vtk/vtk-m/-/tree/master/.gitlab/ci/docker

[vtk-m]: https://gitlab.kitware.com/vtk/vtk-m
