## Support for World vs Physical Coordinates

Add support for putting actors in either the PHYSICAL or the WORLD (default)
coordinate systems by moving PhysicalToWorldMatrix functionality from the
VR-specific rendering modules to the base classes.

Even before this change, any vtkProp3D in PHYSICAL coordinates is transformed
with the PhysicalToWorldMatrix.  With this change, it is possible to supply
such a matrix on the vtkRenderWindow to define the transformation from
physical to world coordinate systems.

See the python test `Rendering/Core/Testing/Python/TestWorldVsPhysicalActors.py`
for an example of a render window interactor can be written to make use of
this functionality.
