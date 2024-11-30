## Default OpenGL profile changed

On Linux (and any platform that uses GLX for OpenGL), VTK will now ask
for `GLX_CONTEXT_PROFILE_MASK_ARB` and `GLX_CONTEXT_CORE_PROFILE_BIT_ARB`
when creating a rendering context.

When these extensions are available, it is possible to use
[RenderDoc](https://renderdoc.org/) to profile the state of the OpenGL
library as each call is made to its API.
RenderDoc has been extremely useful in the development of new shader code.
