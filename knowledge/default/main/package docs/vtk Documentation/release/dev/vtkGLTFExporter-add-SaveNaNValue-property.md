## vtkObjectFactory add SaveNaNValue property

The `vtkGLTFExporter` did export the NaN color in the texture.
This could lead to issue in external viewers, such as MeshLab or Powerpoint.
A new property is here to control weither it exports the NaN color or not.
