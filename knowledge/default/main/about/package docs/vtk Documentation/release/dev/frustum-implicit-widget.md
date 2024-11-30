# Introduce implicit Frustum
The new `vtkFrustum` implicit function represents a frustum ressembling a pyramid with a clipped top. You can shape it by using the setters for its vertical/horizontal angles, i.e. the angles between its forward axis and its top and bottom, or right and left planes respectively. The distance between the near plane and the frustum's origin can also be set. As for all `vtkImplicitFunction`s, you can manipulate its position/orientation/scale by setting a transform.

# Add a new Implicit Frustum Widget
The new `vtkFrustum` has a widget representation. The representation can be manipulated through widget controls:
 - Rotate through the orientation handles
 - Translate through the origin or near plane center handles
 - Adjust vertical/horizontal angles through the "far plane" edges handles
 - Adjust near plane distance through the near plane edges handle.

> ![Screenshot of the Frustum widget in a VTK view](!implicit-frustum-widget.png)
>
> Screenshot of the Frustum widget in a VTK view

Its underlying frustum can be used in any filter relying on implicit functions (i.e. Clip, Slice).
