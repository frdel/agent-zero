# Additional Python Wheels

Python wheels for VTK are available in pypi

```
pip install vtk
```

More wheels can be accessed from the [GitLab Package Registry](https://gitlab.kitware.com/vtk/vtk/-/packages).

To install the **latest release** wheel from the GitLab registry:

```
pip install --extra-index-url https://wheels.vtk.org vtk
```

To install the latest wheel **from master**:

```
pip install --extra-index-url https://wheels.vtk.org vtk --pre --no-cache
```

The wheels available at PyPi are built using the default rendering backend
which leverages any available hardware graphics for generating the scene. There is
also a OSMesa wheel variant that leverages offscreen rendering with OSMesa.
This wheel is being built for both Linux and Windows at this time and bundles
all of the necessary libraries into the wheel. These wheels are intended to be
used by downstream projects in headless, CI-like environments or cloud
application deployments, preventing the need to install any addition system
packages.

:::{versionchanged} 9.4
As of VTK 9.4, OSMesa and EGL support are included by default in the `vtk` wheels and can be selected at runtime. The `vtk-osmesa` wheels are no longer provided, and it is no longer necessary to install `vtk-osmesa`.
:::

```{note}
conda-forge packages are also [available](https://anaconda.org/conda-forge/vtk) and maintained by the community.
```
