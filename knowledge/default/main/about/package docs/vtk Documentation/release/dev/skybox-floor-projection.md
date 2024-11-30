## Infinite floor plane with vtkSkybox

The vtkSkybox class is commonly used for creating a cubemap that encompasses the whole scene.
In addition to the typical cube projection, the vtkSkybox also allows for mapping a single image
texture onto a plane giving the illusion of an infinite ground plane.

In this version, vtkSkybox learned of new properties of scaling the texture mapping of the image
onto the floor projection. `vtkSkybox::SetFloorTexCoordScale` allows users to scale the texture
map in the (u, v) space.

Coincident topology resolution is also built into the skybox allowing coincident geometry to be
displayed on top of the skybox floor.

![](https://www.vtk.org/files/ExternalData/SHA512/3c49faca41da626020e45a14b43b08412bbe200508e568930ee37374ae95f89d633bc9a4c6d4c7b211fffc4bc3ea6f47d42ee97dc3ce236dca389905de00ed05)
