Dashboard Scripts
=================

This page documents how to use the VTK `dashboard` branch in [Git][].
See the [README](README.md) for more information.

[Git]: http://git-scm.com

Using the Dashboard Scripts
---------------------------

The `dashboard` branch contains a dashboard client helper script.
Use these commands to track it:

    $ mkdir -p ~/Dashboards/VTKScripts
    $ cd ~/Dashboards/VTKScripts
    $ git init
    $ git remote add -t dashboard origin https://gitlab.kitware.com/vtk/vtk.git
    $ git pull origin

The `vtk_common.cmake` script contains setup instructions in its
top comments.

Update the `dashboard` branch to get the latest version of this
script by simply running:

    $ git pull

Here is a link to the script as it appears today: [vtk_common.cmake][].

[vtk_common.cmake]: https://gitlab.kitware.com/vtk/vtk/-/tree/dashboard/vtk_common.cmake

Changing the Dashboard Scripts
------------------------------

If you find bugs in the hooks themselves or would like to add new features,
the can be edited in the usual Git manner:

    $ git checkout -b my-topic-branch

Make your edits, test it, and commit the result.  Create a patch file with:

    $ git format-patch origin/dashboard

And post the results in the [Development][] category in the [VTK Discourse][] forum.

[Development]: https://discourse.vtk.org/c/development
[VTK Discourse]: https://discourse.vtk.org/
