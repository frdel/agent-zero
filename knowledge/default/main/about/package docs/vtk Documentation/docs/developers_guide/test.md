Adding Tests
============

This page documents how to add test data while developing VTK with [Git][].
See the [README](README.md) for more information.

[Git]: http://git-scm.com

Setup
-----

The workflow below depends on local hooks to function properly.
Follow the main [developer setup instructions](../develop_quickstart.md#initial-setup)
before proceeding.  In particular, run [SetupForDevelopment.sh][]:

    $ ./Utilities/SetupForDevelopment.sh

[SetupForDevelopment.sh]:../../../../Utilities/SetupForDevelopment.sh

Workflow
--------

Our workflow for adding data integrates with our standard Git
[development process](develop.md).  Start by
[creating a topic](develop.md#create-a-topic).
Return here when you reach the "edit files" step.

These instructions follow a typical use case of adding a new
test with a baseline image.

### Writing new tests

All new features that go into VTK must be accompanied by tests. This ensures
that the feature works on many platforms and that it will continue to work as
VTK evolves.

Tests for the classes in each module of VTK are placed underneath the module's
Testing/<Language> subdirectory. Modules that the tests depend upon beyond
those that the module itself depends upon are declared with the TEST_DEPENDS
argument in the `vtk.module`   file. Test executables are added to VTK's build
system by naming them in the `CMakeLists.txt` files in each Testing/<Language>
directory. In those `CMakeLists`, standard `add_executable()` + `add_test()` command
pairs could be used, but the following macros defined in `vtkModuleTesting.cmake`
are preferable as they consolidate multiple tests together, participate in
VTK's modular build scripts, and ensure consistency:

-   {cmake:command}`vtk_add_test_cxx`
-   {cmake:command}`vtk_add_test_mpi`
-   {cmake:command}`vtk_add_test_python`

Tests indicate success to CTest by returning `EXIT_SUCCESS` (0) and failure by
returning `EXIT_FAILURE` (1). How the test determines what result to return is
up to the developer. VTK contains a number of utilities for this task. For
example, vtkRegressionTester is a helper class that does a fuzzy comparison of
images drawn by VTK against known good baseline images and returns a metric
that can be simply compared against a numeric threshold.


Many tests require data files to run. The image comparison tests for example
need baseline images to compare against, and many tests open up one or more
files to visualize.

The source code and data file versions are kept in sync because the
Testing/Data directory contains, instead of the real files, similarly named
files which contain only the SHA512 hash of the matching data files. During the
build process, when CMake sees that a required data file is not available, it
downloads it into the directory defined by the ExternalData_OBJECT_STORES cmake
configuration entry. The test executables read all data from there. The default
setting for ExternalData_OBJECT_STORES is the ExternalData directory underneath
the VTK build tree.

To make a change to VTK that modifies or adds a new test data file, place the
new version in the Testing/Data or directory (for input data files) or
Module/Name/Testing/Data (for regression test images), and build (or run
cmake). CMake will do the work of moving the original out of the way and
replacing it with an SHA512 link file. When you push the new link file to Gitlab,
`git pre-commit` hooks push the original file up to Kitware's data service, where
everyone can retrieve it.

### Add Test ###

1.  Write a new test, e.g.

        $ edit Some/Module/Testing/Cxx/MyTest.cxx

2.  Edit the corresponding `CMakeLists.txt` file:

        $ edit Some/Module/Testing/Cxx/CMakeLists.txt

    and add the test in a `vtk_add_test_...` call (which references
    baselines automatically).

3.  For tests not using such a call, reference the data file in an
    `ExternalData_add_test` call.  Specify the file inside `DATA{...}`
    using a path relative to the test directory:

        $ edit Some/Module/Testing/Cxx/CMakeLists.txt
        ExternalData_add_test("${_vtk_build_TEST_DATA_TARGET}"
          NAME ${_vtk_build_test}Cxx-MyTest
          COMMAND <VTK_MODULE_NAME>CxxTests MyTest
                  ... -V DATA{../Data/Baseline/MyTest.png,:} ...
          )

4.  Some tests may require additional files not referenced on the command line.
    For these files, add references to a `vtk_module_test_data` call (usually
    in the `Testing` parent directory). For example, adding
    `Testing/Data/lines.vtp` would mean adding `Data/lines.vtp` entry to the
    call (the `Testing` directory is part of the path that is looked in
    automatically.

        vtk_module_test_data(
          Data/lines.vtp)

Notes:

* If the data file references other data files, e.g. `.mhd -> .raw`,
  read the [ExternalData][] module documentation on "associated" files.
* Multiple baseline images and other series are handled automatically
  when the reference ends in the `,:` option.  Read [ExternalData][]
  module documentation for details.

[ExternalData]: https://cmake.org/cmake/help/latest/module/ExternalData.html

### Build and Run the Test ###

If you already have a data file, skip to the [next step](#add-data) to add it.
Otherwise, use the following steps to produce a test baseline image file.
We assume a build tree has been previously generated by CMake.

1.  Switch to the build tree:

        $ cd ../VTK-build

2.  Run CMake:

        $ cmake .

    Since we have not yet created the baseline image data file, CMake
    will warn that it does not exist but proceed to generate the test
    anyway.

3.  Build

        $ make

4.  Run the test

        $ ctest -R MyTest

    It will fail but place the baseline image in `Testing/Temporary`.

5.  Switch back to the source tree:

        $ cd ../VTK

### Add Data ###

Copy the data file into your local source tree.

    $ mkdir -p Some/Module/Testing/Data/Baseline
    $ cp ../VTK-build/Testing/Temporary/MyTest.png Some/Module/Testing/Data/Baseline

### Run CMake ###

1.  Switch to the build tree:

        $ cd ../VTK-build

2.  Run CMake:

        $ cmake .

    CMake will [move the original file](#externaldata).  Keep your own
    copy if necessary.  See [below](#recover-data-file) to recover the
    original file.

    During configuration CMake will display a message such as:

        Linked Some/Module/Testing/Data/Baseline/MyTest.png.sha512 to ExternalData SHA512/...

    This means that CMake converted the file into a data object referenced
    by a "content link" named like the original file but with a `.sha512`
    extension.  CMake also [renamed the original file](#externaldata).

3.  Build

        $ make

    During the build, the [ExternalData][] module will make the data
    file available where the test expects to find it.

4.  Run the test

        $ ctest -R MyTest

    It should pass using the new data file.

5.  Switch back to the source tree:

        $ cd ../VTK

### Commit ###

Continue to [create the topic](develop.md#create-a-topic) and edit other
files as necessary.  Add the content link and commit it along with the
other changes:

    $ git add Some/Module/Testing/Data/Baseline/MyTest.png.sha512
    $ git add Some/Module/Testing/Data/CMakeLists.txt
    $ git commit

The local `pre-commit` hook will display a message such as:

    Some/Module/Testing/Data/Baseline/MyTest.png.sha512: Added content to Git at refs/data/SHA512/...
    Some/Module/Testing/Data/Baseline/MyTest.png.sha512: Added content to local store at .ExternalData/SHA512/...
    Content link Some/Module/Testing/Data/Baseline/MyTest.png.sha512 -> .ExternalData/SHA512/...

This means that the pre-commit hook recognized that the content link
references a new data object and [prepared it for upload](#pre-commit).

### Push ###

Follow the instructions to [share the topic](develop.md#share-a-topic).
When you push it to GitLab for review using

    $ git gitlab-push

part of the output will be of the form:

    *       ...:refs/data/...      [new branch]
    *       HEAD:refs/heads/my-topic  [new branch]
    Pushed refs/data/... and removed local ref.

This means that the `git-gitlab-push` script pushed the topic
and [uploaded the data](#git-gitlab-push) it references.

Options for `gitlab-push` include:
* `--dry-run`: Report push that would occur without actually doing it
* `--no-topic`: Push the data referenced by the topic but not the topic itself

Note: One must `git gitlab-push` from the same work tree as was used
to create the commit.  Do not `git push` to another computer first and
try to push to GitLab from there because the data will not follow.

Building
--------

### Download ###

For the test data to be downloaded and made available to the tests in
your build tree the `VTKData` target must be built.  One may build the
target directly, e.g. `make VTKData`, to obtain the data without a
complete build.  The output will be something like

    -- Fetching ".../ExternalData/SHA512/..."
    -- [download 100% complete]
    -- Downloaded object: "VTK-build/ExternalData/Objects/SHA512/..."

The downloaded files appear in `VTK-build/ExternalData` by default.

### Local Store ###

It is possible to configure one or more local ExternalData object
stores shared among multiple builds.  Configure for each build the
advanced cache entry `ExternalData_OBJECT_STORES` to a directory on
your local disk outside all build trees, e.g. `/home/user/.ExternalData`:

    $ cmake -DExternalData_OBJECT_STORES=/home/user/.ExternalData ../VTK

The [ExternalData][] module will store downloaded objects in the local
store instead of the build tree.  Once an object has been downloaded
by one build it will persist in the local store for re-use by other
builds without downloading again.

Discussion
----------

A VTK test data file is not stored in the main source tree under version
control.  Instead the source tree contains a "content link" that refers
to a data object by a hash of its content.  At build time the
[ExternalData][] module fetches data needed by enabled tests.
This allows arbitrarily large data to be added and removed without
bloating the version control history.

The above [workflow](#workflow) allows developers to add a new data file
almost as if committing it to the source tree.  The following subsections
discuss details of the workflow implementation.

### ExternalData ###

While [CMake runs](#run-cmake) the [ExternalData][] module evaluates
[DATA{} references](#add-test).  VTK sets in [vtkExternalData.cmake][]
the `ExternalData_LINK_CONTENT` option to `SHA512` to enable automatic
conversion of raw data files into content links.  When the module detects
a real data file in the source tree it performs the following
transformation as specified in the module documentation:

* Compute the SHA512 hash of the file
* Store the `${hash}` in a file with the original name plus `.sha512`
* Rename the original file to `.ExternalData_SHA512_${hash}`

The real data now sit in a file that we [tell Git to ignore](/.gitignore).
For example:

    $ cat Some/Module/Testing/Data/Baseline/.ExternalData_SHA512_477e6028* |sha512sum
    477e6028...  -
    $ cat Some/Module/Testing/Data/Baseline/MyTest.png.sha512
    477e6028...

[vtkExternalData.cmake]: ../../../../CMake/vtkExternalData.cmake

#### Recover Data File ####

To recover the original file after running CMake but before committing,
undo the operation:

    $ cd Some/Module/Testing/Data/Baseline
    $ mv .ExternalData_SHA512_$(cat MyTest.png.sha512) MyTest.png

### pre-commit ###

While [committing](#commit) a new or modified content link the
[pre-commit][] hook moves the real data
object from the `.ExternalData_SHA512_${hash}` file left by the
[ExternalData][] module to a local object repository stored in a
`.ExternalData` directory at the top of the source tree.

The hook also uses Git plumbing commands to store the data object
as a blob in the local Git repository.  The blob is not referenced
by the new commit but instead by `refs/data/SHA512/${hash}`.
This keeps the blob alive in the local repository but does not add
it to the project history.  For example:

    $ git for-each-ref --format="%(refname)" refs/data
    refs/data/SHA512/477e6028...
    $ git cat-file blob refs/data/SHA512/477e6028... | sha512sum
    477e6028...  -

[pre-commit]:../../../../Utilities/Scripts/pre-commit

### git gitlab-push ###

The `git gitlab-push` command is actually an alias for the
[git-gitlab-push][] script.
In addition to pushing the topic branch to GitLab the script also detects
content links added or modified by the commits in the topic.
It reads the data object hashes from the content links and looks for
matching `refs/data/` entries in the local Git repository.

The script pushes the matching data objects to your VTK GitLab fork.
For example:

    $ git gitlab-push --dry-run --no-topic
    *       refs/data/SHA512/477e6028...:refs/data/SHA512/477e6028...   [new branch]
    Pushed refs/data/SHA512/477e6028... and removed local ref.

A GitLab webhook that triggers whenever a topic branch is pushed checks
for `refs/data/` in your VTK GitLab fork, fetches them, erases the refs
from your fork, and uploads them to a location that we
tell ExternalData to search in [vtkExternalData][] at build time.

To verify that the data has been uploaded as expected, you may direct
a web browser to the location where ExternalData has uploaded the files.
For VTK, that location is currently
`http://www.vtk.org/files/ExternalData/SHA512/XXXX` where `XXXX` is the
complete SHA512 hash stored in the content link file (e.g., the text in
`MyTest.png.sha512`).

[git-gitlab-push]:../../../../Utilities/GitSetup/git-gitlab-push

### Publishing Data for an External Branch ###

The above [workflow](#workflow) works well for developers working on a
single machine to contribute changes directly to upstream VTK.  When
working in an external branch of VTK, perhaps during a long-term topic
development effort, data objects need to be published separately.

The workflow for adding data to an external branch of VTK is the same
as the above through the [commit](#commit) step, but diverges at the
[push](#push) step because one will push to a separate repository.
Our ExternalData infrastructure intentionally hides the real data files
from Git so only the content links (`.sha512` files) will be pushed.
The real data objects will still be left in the `.ExternalData/SHA512`
directory at the top of the VTK source tree by the
[pre-commit](#pre-commit) hook.

The `.ExternalData` directory must be published somewhere visible to
other machines that want to use the data, such as on a web server.
Once that is done then other machines can be told where to look for
the data, e.g.

    cmake ../VTK "-DExternalData_URL_TEMPLATES=https://username.github.io/VTK/ExternalData/%(algo)/%(hash)

In this example we assume the files are published on a [Github Pages][]
`gh-pages` branch in `username`'s fork of VTK.

Within the `gh-pages` branch the files are placed at
`ExternalData/SHA512/$sha512sum` where `$sha512sum` is the SHA512 hash of the content
(these are the same names they have in the `.ExternalData` directory in
the original source tree).

[Github Pages]: https://help.github.com/articles/creating-project-pages-manually
