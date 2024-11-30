# Building documentation

This section outlines how to locally build both the user and developer guides and the C++ API
documentation for VTK.

## User and developer guides

VTK's user and developer guides are automatically built and deployed to https://docs.vtk.org
every time the `master` branch is updated by leveraging the integration with the
_Read the Docs_ service.

To locally build the documentation:

::::::{tab-set}

:::::{tab-item} Without VTK build tree

1. [Download](/build_instructions/build.md#obtaining-the-sources) the VTK sources.

2. Create and activate a virtual environment.

::::{tab-set}

:::{tab-item} Linux/macOS
:sync: linux-or-macos

```shell
cd Documentation/docs

python3 -m venv .venv
source .venv/bin/activate
```

:::

:::{tab-item} Windows
:sync: windows

```bat
cd Documentation\docs

py -m venv .venv
.\.venv\Scripts\activate
```

`py -m venv` executes venv using the latest Python interpreter you have installed.
For more details, read the [Python Windows launcher](https://docs.python.org/3/using/windows.html#launcher) docs.

:::

::::

3. Install dependencies using pip.

::::{tab-set}

:::{tab-item} Linux/macOS
:sync: linux-or-macos

```shell
python3 -m pip install -r requirements.txt
```

:::

:::{tab-item} Windows
:sync: windows

```bat
py -m pip install -r requirements.txt
```

:::

::::

4. Build the documentation as web pages.

```shell
make html
```

5. Open `_build/html/index.html` in a web browser.

::::{tab-set}

:::{tab-item} Linux
```shell
xdg-open _build/html/index.html
```

:::

:::{tab-item} macOS

```shell
open _build/html/index.html
```

:::

:::{tab-item} Windows
:sync: windows

```bat
start _build\html\index.html
```

:::

::::

:::::

:::::{tab-item} With VTK build tree

:::{important}
In order to successfully build the VTK documentation using the instructions below, you will
need to install the required Python packages.

To ensure that you have the correct dependencies installed in the Python environment associated
with the VTK build tree, please run `pip install -r Documentation\docs\requirements.txt` or
`pip install --user -r Documentation\docs\requirements.txt`.

If updating your system installation of Python is not feasible or you prefer not to do so,
we recommend following the `Without VTK build tree` approach instead.
:::

1. [Download](/build_instructions/build.md#obtaining-the-sources) VTK sources.

2. [Configure](/build_instructions/build.md#configure) VTK by setting the `VTK_BUILD_SPHINX_DOCUMENTATION`
   option to `ON`.

2. Build the `SphinxDoc` target.

:::::

::::::

:::{hint}
Automatic build of preview documentation each time a merge request is submitted is not yet
supported due to [limitation](https://docs.readthedocs.io/en/stable/guides/pull-requests.html#limitations)
of the _Read The Docs_ service that does not yet support self-hosted GitLab deployment.

Solutions to address this are being discussed in https://github.com/readthedocs/readthedocs.org/issues/9464.
:::

## C++ API documentation

The C++ API documentation is built and uploaded to https://vtk.org/doc/nightly/html/index.html
when the `master` branch is updated.

To locally build the documentation:

1. Install Doxygen

2. [Download](/build_instructions/build.md#obtaining-the-sources) the VTK sources.

3. [Configure](/build_instructions/build.md#configure) VTK by setting the `VTK_BUILD_DOCUMENTATION` option to `ON`.

3. Build the `DoxygenDoc` target.

## Targets

After configuring the VTK using CMake, the following targets may be used to
build documentation for VTK:

  * `DoxygenDoc` - build the doxygen documentation from VTK's C++ source files
  (`VTK_BUILD_DOCUMENTATION` needs to be `ON` for the target to exist).
  * `SphinxDoc` - build the sphinx documentation for VTK.
  (`VTK_BUILD_SPHINX_DOCUMENTATION` needs to be `ON` for the target to exist).
