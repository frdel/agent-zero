# Introduce implicit Annulus
The new `vtkAnnulus` implicit function represents an infinite annulus (two co-axial cylinders). It exposes getters and setters for its axis, origin, and inner/outer radii parameters. Changing those will automatically update the base `vtkImplicitFunction`'s transform.

# Add a new Implicit Annulus Widget
The new `vtkAnnulus` has a widget representation. The representation can be manipulated through widget controls:
 - Rotate through the axis handle
 - Translate through the center handle
 - Scale through the outline handle
 - Adjust inner/outer radii through the cone edges handles

Its underlying annulus can be used in any filter relying on implicit functions (i.e. Clip, Slice).
