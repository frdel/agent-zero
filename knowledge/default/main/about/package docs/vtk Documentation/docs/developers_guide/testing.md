# Regression Testing

##  Testing and dashboard submitter setup

Regression testing in VTK takes the form of a set of programs, that are included  in the VTK source code and enabled in builds configured through CMake to have the `VTK_BUILD_TESTING` flag turned on. Test pass/fail results are returned to CTest via a test program's exit code. VTK contains helper classes that do specific checks, such as comparing a produced image against a known valid one, that are used in many of the regression tests.  Test results may be submitted to Kitware's CDash instance, were they will be gathered and displayed at <http://open.cdash.org/index.php?project=VTK>

All proposed changes to VTK are automatically tested on Windows, Mac and Linux machines. All changes that are merged into the master branch are subsequently tested again by more rigorously configured Windows, Mac and Linux continuous dashboard submitters. After 9PM Eastern Time, the master branch is again tested by a wider set of machines and platforms. These results appear in the next day's page.

At each step in the code integration path the developers who contribute and merge code are responsible for checking the test results to look for problems that the new code might have introduced. Plus signs in CDash indicate newly detected  problems. Developers can correlate problems with contributions by logging in to CDash. Submissions that contain a logged in developer's change are highlighted with yellow dots.

It is highly recommended that developers test changes locally before submitting them. To run tests locally:

1.  Configure with `VTK_BUILD_TESTING` set ON

    The exact set of tests created depends on many configuration options. Tests in non-default modules are only tested when those modules are purposefully enabled, the smoke tests described in the Coding Style section above are enabled only when the python or Tcl interpreter is installed, tests written in wrapped languages are only enabled when wrapping is turned on, etc.

1.  Build. 

    VTK tests are only available from the build tree.

1.  Run ctest at the command line in the build directory or make the TESTING target in Visual Studio.

    As ctest runs the tests it prints a summary. You should expect 90% of the tests or better to pass if your VTK is configured correctly. Detailed results (which are also printed if you supply a --V argument to ctest) are put into the Testing/Temporary directory. The detailed results include the command line that ctest uses to spawn each test. Other particularly useful arguments are:
    ```bash
    --R TestNameSubstringToInclude to choose tests by name

    --E TestNameSubstringToExclude to reject tests by name

    --I start,stop,step to run a portion of the tests

    --j N to run N tests simultaneously.
    ```

Dashboard submitting machines work at a slightly higher level of abstraction that adds the additional stages of downloading, configuring and building VTK before running the tests, and submitting all results to CDash afterward. With a build tree in place you can run "ctest --D Experimental"  to run at this level and submit the results to the experimental section of the VTK dashboard or "ctest --M Experimental -T Build --T Submit" etc to pick and choose from among the stages. When setting up a test submitter machine one should start with the experimental configuration and then, once the kinks are worked out, promote the submitter to the Nightly section.

The volunteer machines use cron or Windows task scheduler to run CMake scripts that configure a VTK build with specific options, and then run ctest --D as above. Within CDash, you can see each test machine's specific configuration by clicking on the Advanced View and then clicking on the note icon in the Build Name column. This is a useful starting point when setting up a new submitter. It is important that each submitter's dashboard script include the name of the person who configures or maintains the machine so that, when the machine has problems, the dashboard maintainer can address it.

For details about the Continuous Integration infrastructure hosted at Kitware see [here](git/develop.md#continuous-integration).

## Run-time environment of tests using `ctest`

When running a test using `ctest`, an extra empty environment variable is set: `VTK_TESTING`. One
can catch this environment variable and know that the code is executed under ctest. In particular,
`VTK_TESTING` is used to disable anti-aliasing in the constructor of `vtkOpenGLRenderWindow` for the
sake of making comparing image baseline more robust against graphics drivers discrepancies.
