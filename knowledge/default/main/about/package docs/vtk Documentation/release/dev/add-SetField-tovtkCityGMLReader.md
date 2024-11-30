# Add SetField static methods to vtkCityGMLReader

vtkCityGMLReader uses field arrays to store texture paths or material colors
for polydata in a multiblock dataset. The SetField static helper functions
are used by the reader and now can be used to manually build a dataset using
the same format.
