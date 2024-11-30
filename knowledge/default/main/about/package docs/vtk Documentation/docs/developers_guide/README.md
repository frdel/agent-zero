---
orphan: true
---

VTK Git Usage
=============

VTK version tracking and development is hosted by [Git](http://git-scm.com).
Please select a task for further instructions:

Main Tasks
----------
* [Install Git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)
  Git 1.7.2 or greater is preferred (required for development)

* [Download VTK](download.md) - Users start here

* [Develop VTK](develop.md) - Contributors start here

Other Tasks
-----------

* [Review Changes](https://gitlab.kitware.com/vtk/vtk/-/merge_requests) -
  VTK GitLab Merge Requests

* [Test VTK](dashboard.md) - CDash client setup

* [Learn Git](http://public.kitware.com/Wiki/Git/Resources) -
  Third-party documentation

Branches
--------

The upstream VTK repository has the following branches:

* `master`: Development (default)
* `release`: Maintenance of latest release
* `nightly-master`: Follows `master`, updated at `01:00 UTC`
* `hooks`: Local commit hooks
   ([placed](http://public.kitware.com/Wiki/Git/Hooks#Local) in `.git/hooks`)
* `dashboard`: Dashboard script ([setup](dashboard.md) a CDash client)
