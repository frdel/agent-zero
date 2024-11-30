# About

## Overview

The Visualization Toolkit (VTK) is a robust and open-source software system
that provides advanced features in 3D computer graphics, image processing,
modeling, volume rendering, and scientific visualization. It offers threaded
and distributed-memory parallel processing for scalability and better
performance.

VTK is a cross-platform library that can run on many operating systems,
including Windows, macOS, Linux, and even the web and mobile devices.

VTK is widely used in both academic and commercial settings, as well as in
government institutions such as Los Alamos National Lab and CINECA. The
software was originally published in the textbook titled "The Visualization
Toolkit, an Object-Oriented Approach to 3D Graphics" and has grown
significantly since its release in 1994 with an extensive worldwide user base.

VTK maintains a high-quality software process, which includes CMake, CTest,
CDash, and CPack. The software is written in C++ with additional language
bindings to reach a broader audience, with an excellent interoperability with
Python.

As open source software, VTK is free to use for any purpose. Technically, VTK
has a BSD-style license, which imposes minimal restrictions for both open and
closed source applications.

If you're interested in exploring the growth and usage patterns of VTK, we
provide you with our statistics. The statistics are available on Open Hub, a
platform focused on community-driven software, and PyPI stats, which provides
download statistics for VTK packages. By analyzing these statistics, you can
gain insights into the community's size, VTK's adoption rates, and popularity.
Check out the links below for more information:
* [Open Hub](https://www.openhub.net/p/vtk)
* [PyPI stats](https://pypistats.org/packages/vtk)

## Features

VTK provides a comprehensive set of features that support visualization,
modeling, and data analysis. Here are some highlights:

::::{grid} 2

:::{grid-item-card} Filters
VTK's filter-based architecture processes data by transforming and manipulating
it through a pipeline of successive filters. This approach produces derived
data that can be rendered using VTK's graphics system. Filters can be combined
into a dataflow network, which enables a flexibly configurable workflow.
:::

:::{grid-item-card} Graphics System
VTK provides a sophisticated rendering abstraction layer over the underlying
graphics library (OpenGL with experimental support for WebGL), simplifying the
creation of engaging visualizations.
:::

:::{grid-item-card} Data Model
VTK’s core data model has the ability to represent almost any
real-world problem related to physical science. The fundamental data structures
are particularly well-suited to medical imaging and engineering work that
involves finite difference and finite element solutions.
:::

:::{grid-item-card} Data Interaction
VTK provides several tools for interactive data exploration and analysis,
including 3D widgets, interactors, and 2D widget libraries integration like Qt.
These enable powerful user interaction capabilities, making it easier to
understand the content, shape, and meaning of data.
:::

:::{grid-item-card} 2D Plots and Charts
VTK supports a full set of 2D plot and chart types for tabular data
visualization. It also includes picking and selection capabilities, allowing
users to query data interactively. VTK's excellent interoperability with Python
and Matplotlib further increases its flexibility.
:::

:::{grid-item-card} Parallel Processing
VTK offers excellent support for scalable distributed-memory parallel
processing under MPI. VTK filters implement finer-grained parallelism using
vtkSMP for coarse-grained threading and vtk-m for fine-grained processing on
many-core and GPU architectures. These parallel processing capabilities make
VTK highly efficient and suited for processing large data sets.
:::
::::

## License

VTK is distributed under the OSI-approved BSD 3-clause License. See
[here](https://gitlab.kitware.com/vtk/vtk/-/blob/master/Copyright.txt) for
details.

## Citing

When citing VTK in your scientific research, please mention the following work to support increased visibility and dissemination of our software:

    Schroeder, Will; Martin, Ken; Lorensen, Bill (2006), The Visualization Toolkit (4th ed.), Kitware, ISBN 978-1-930934-19-1

For your convenience here is a bibtex entry:

```bibtex
@Book{vtkBook,
  author    = "Will Schroeder and Ken Martin and Bill Lorensen",
  title     = "The Visualization Toolkit (4th ed.)",
  publisher = "Kitware",
  year      = "2006",
  isbn      = "978-1-930934-19-1",
}
```

To cite a specific filter, check for extra references in the included headers or the [doxygen](https://vtk.org/doc/nightly/html) documentation of the filter.

## History

**2016 - Rendering Backend in ParaView 5.0**

See [Brand-New Rendering Backend in ParaView 5.0](https://www.kitware.com/kitware-unleashes-brand-new-rendering-backend-in-paraview-5-0/).

**2014 - Transition from OpenGL to OpenGL2**

See [New OpenGL Rendering in VTK](https://www.kitware.com/new-opengl-rendering-in-vtk).

**1993 - Origin**

VTK was originally part of the textbook [The Visualization Toolkit An
Object-Oriented Approach to 3D
Graphics](https://vtk.org/documentation/#textbook). Will Schroeder, Ken Martin,
and Bill Lorensen—three graphics and visualization researchers—wrote the book
and companion software on their own time, beginning in December 1993, with
legal permission from their then-employer, GE R&D. The motivation for the book
was to collaborate with other researchers and develop an open framework for
creating leading-edge visualization and graphics applications.

VTK grew out of the authors’ experiences at GE, particularly with the LYMB
object-oriented graphics system. Other influences included the VISAGE
visualization system developed by Schroeder et. al; the Clockworks
object-oriented computer animation system developed at Rensselaer Polytechnic
Institute; and the Object-Oriented Modeling and Design book, which Bill
Lorensen co-authored.

After the core of VTK was written, users and developers around the world began
to improve and apply the system to real-world problems. In particular, GE
Medical Systems and other GE businesses contributed to the system, and
researchers such as Dr. Penny Rheinghans began to teach with the book. Other
early advocates include Jim Ahrens at Los Alamos National Laboratory and
generous oil and gas supporters.

To address what was becoming a large, active, and world-wide community, Ken and
Will—along with Lisa Avila, Charles Law, and Bill Hoffman—left GE in 1998 to
found Kitware, Inc. Since that time, hundreds of additional developers have
turned VTK into what is now the premier visualization system in the world.
Sandia National Laboratories, for example, has been a strong supporter and
co-developer, revamping 2D charting and information visualization in VTK.

## Acknowledgments

Many institutions have taken part in the development of VTK. Some of the most fundamental work came from the following:
- [Kitware](https://www.kitware.com)
- [Los Alamos National Lab (LANL)](http://www.lanl.gov)
- [National Library of Medicine (NLM)](http://www.nlm.nih.gov)
- [Department of Energy (DOE) ASC Program](http://www.cio.energy.gov/high-performance-computing.htm)
- [Sandia National Laboratories](http://www.sandia.gov)
- [Army Research Laboratory (ARL)](http://www.arl.army.mil/www/default.htm)

Special thanks to all the [contributors](https://github.com/Kitware/VTK/graphs/contributors) !

## Commercial Use

We invite commercial entities to use VTK.

VTK is part of Kitware’s collection of commercially supported open-source platforms for software development.

VTK’s License makes Commercial Use Available
* VTK is a free open source software distributed under a [BSD style license](#license).
* The license does not impose restrictions on the use of the software.
* VTK is NOT FDA approved. It is the users responsibility to ensure compliance with applicable rules and regulations.

## Contact Us

We want to hear from you! If you have any questions, suggestions or bug reports
regarding VTK, there are several communication channels available for you:

**VTK Forum**

Visit the [VTK Discourse](https://discourse.vtk.org) forum for community-driven support,
to share your experiences, exchange ideas and best practices, and to discuss
challenges.

**Issue Tracker**

Use our [public issue tracker](https://gitlab.kitware.com/vtk/vtk/-/issues) to
report any bugs or request enhancements. This tracker is a ticket-based system
that allows you to keep track of your issues and follow up on their progress.

**Commercial and Confidential Consulting**

For commercial or confidential consulting related to VTK or any of our other
products and services, please contact
[Kitware's advanced support team](https://www.kitware.com/contact/advanced-support/)
for personalized assistance.
