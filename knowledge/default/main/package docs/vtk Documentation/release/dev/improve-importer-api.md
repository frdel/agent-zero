Importer API improvements
=========================

The vtkImporter API has been improved
to provide a boolean output to vtkImporter::Update.

vtkImporter::UpdateAtTimeValue has been added.

vtkImporter::Read has been deprecated.
vtkImporter::UpdateTimeStep has been deprecated.

vtkImporter implementation can now position an Update status
using SetUpdateStatus, especially when there is a failure.
