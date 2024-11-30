## CGNSReader: Load surface elements stored as Element_t entries

The CGNS reader has a new option `LoadSurfacePatch` that allows to read 2D
elements that are not  `BC_t` nodes(handled by the LoadBndPatch option)  but
rather `Element_t` nodes.  This allows to read boundary elements no matter if
boundary conditions are assigned to them.
