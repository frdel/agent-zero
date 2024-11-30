## OpenXR Controller Model Rendering

VTK now supports basic rendering of controller models under OpenXR.

While OpenXR does not yet provide any api for rendering controller models
in the same way that OpenVR does, this change provides a way for VTK to
render glTF controller models by using the currently active interaction
profile to index a table of model asset files.

No models are included in the repository, but an archive containing models
for a subset of supported interaction profiles is available for download
from paraview.org.  This archive can be extracted into any VTK/ParaView
build/install tree, allowing VTK to discover and render them automatically.
This basic set of models will be included by default in ParaView binary
downloads.

See `VTK/Rendering/OpenXR/README.md` for more details.
