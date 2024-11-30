# Fix deserialization bug in vtkCollection

Fixes a bug in the deserialization of `vtkRenderer`. When an actor in a renderer was replaced with another actor,
and the scene reserialized with `vtkObjectManager`, the deserializer was unable to detect that the actor had
changed. Instead, the renderer continued to show the old actor. This bug in deserialization of vtkCollection
is now fixed.
