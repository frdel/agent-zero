## Add Alembic scene exporter

The IO/Alembic module now provides a new scene exporter for the [Alembic file format](https://www.alembic.io/).
This format is used for dynamic scene and complex geometry exchange for 3D modeling packages.

The class `vtkAlembicExporter` exports the current visible scene to an ".abc" file. This includes
all visible polygonal geometry, with vertex colors and texture coordinates. If a colormap has been
applied, a texture containing the colormap is also saved as a ".png" file. The camera position and
orientation is also exported. Blender 3.6 imports these scene files, and other modeling packages
like 3D Studio Max and Maya also have Alembic importers.
