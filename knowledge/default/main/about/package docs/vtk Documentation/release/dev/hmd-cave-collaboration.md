## Support collaboration among CAVEs

The RenderingParallel module now provides support for synchronizing collections of actors among the synchronized renderers.  The first such supported actor type is vtkOpenGLAvatar, which lays the foundation for supporting collaboration among users of HMD-based VR and CAVEs.

To add a new type of synchronizable actor in the future, you can simply subclass vtkSynchronizableActors and implement the four api methods:

* InitializeRenderer
* CleanUpRenderer
* SaveToStream
* RestoreFromStream

And then update vtkSynchronizedRenderers::EnableSynchronizableActors to instantiate your new class.

Other minor improvements supporting collaboration in CAVEs include:

* vtkFlagpoleLabel now supports CAVEs by making the label face the camera eye point (rather than the desktop camera position) when in off-axis projection mode
* vtkVRCollaborationClient now allows customizing the default initial avatar up vector from the new default of [0, 1, 0]
* vtkVRCollaborationClient now allows specifying an arbitrary object as the source of Move3DEvents used to share local pose with collaborators
* vtkOpenGLAvatar now provides api access to get the associated avatar label
