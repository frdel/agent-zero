# Using Jupyter

When it comes to rendering with VTK in Jupyter, there are several options.

To harness the full power of VTK in Jupyter, you may want to leverage
[PyVista](https://docs.pyvista.org/) and [Trame](https://kitware.github.io/trame/index.html).
PyVista exposes a high-level interface to VTK for plotting and when combined
with Trame, empowers users to bring the full power of VTK to a Jupyter
notebook. We have
[a post on the VTK discourse about this](https://discourse.vtk.org/t/pyvista-trame-jupyter-3d-visualization/10610). See PyVista's documentation
for more information on using PyVista's wrappings of VTK in Jupyter.

[itkwidgets](https://itkwidgets.readthedocs.io/en/latest) is one example of
a domain-specific Jupyter viewer built on VTK. To try out itkwidgets, check
[this example](https://colab.research.google.com/github/InsightSoftwareConsortium/itkwidgets/blob/main/examples/integrations/vtk/vtkImageData.ipynb).

If you are running the script in a Linux/Windows machine without a display or a GPU, VTK will automatically
select an appropriate OpenGL render window class. Please learn more about how you can influence the
render window selection process in [](/advanced/runtime_settings.md#opengl)
