---
orphan: true
---

Download VTK with Git
=====================

This page documents how to download VTK source code through [Git][].
See the [README](README.md) for more information.

[Git]: http://git-scm.com

Clone
-----

Clone VTK using the commands:

    $ git clone https://gitlab.kitware.com/vtk/vtk.git VTK
    $ cd VTK
    $ git submodule update --init

Update
------

Users that have made no local changes and simply want to update a
clone with the latest changes may run:

    $ git pull

Avoid making local changes unless you have read our [developer instructions][].

[developer instructions]: develop.md

Release
-------

After cloning your local repository will be configured to follow the upstream
`master` branch by default.  One may create a local branch to track the
upstream `release` branch instead, which should guarantee only bug fixes to
the functionality available in the latest release:

    $ git checkout --track -b release origin/release

This local branch will always follow the latest release.
Use the [above instructions](#update) to update it.
Alternatively one may checkout a specific release tag:

    $ git checkout v6.2.0

Release tags never move.  Repeat the command with a different tag to get a
different release.  One may list available tags:

    $ git tag

and then checkout any tag listed.
