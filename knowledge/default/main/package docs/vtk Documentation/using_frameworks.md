# Using existing frameworks and applications

There are many VTK-based, free, open-source applications for scientific,
bio-medical and medical image visualization and processing; several of them are
extensible frameworks that can be customized for particular use cases.
[ParaView](https://paraview.org), [Trame](https://kitware.github.io/trame/index.html),
[PyVista](https://docs.pyvista.org), and [3D Slicer](https://www.slicer.org/)
are examples. Therefore, it is worth
evaluating if any of these would allow you to address your challenges. This
would save time by avoiding redeveloping everything from scratch and by
capitalizing on large communities with thousands of experts.

Generally, the default (complex, but powerful) user interface of these applications
allows one to figure out the complete workflow. Once one knows exactly what and how
to do it, they can create a small Python scripted module that automates most of the
steps and provides a simplified user interface.
