# Motivation

`Ghost cells` are layers of cells at boundaries of pieces of a
dataset. These cells are used by data parallel algorithms, to ensure
the correctness of their results. For instance, consider an algorithm
that computes the external faces of a dataset. Consider also that the
algorithm runs in parallel on several nodes, each node processing a
piece of the original dataset. This operation would produce incorrect
faces at boundaries of pieces. Ghosts cells can prevent this. See the
following [wiki entry](http://www.vtk.org/Wiki/VTK/Parallel_Pipeline)
for a more detailed description of ghost cells.

`Blanking cells` are used to specify that certain pieces of a grid
are not part of the data. For instance, a regular dataset with a hole
in it could be specified by blanking the cells that cover the
hole. Blanking cells are supported for `vtkStructuredGrid` and `vtkUniformGrid`.

We change how ghost and blanked cells are stored to:

1. better support blanking: in the past blanked cells were stored as
   members of `vtkStructuredGrid` and `vtkUniformGrid`. This
   created the need for special processing when these arrays needed to
   be passed between algorithms or processes. Now, blanked cells are
   marked with a bit in a field array. Field arrays are passed
   automatically between algorithms and processes

2. provide binary compatibility with VisIt: VTK now uses the
   [same bits as VisIt](http://www.visitusers.org/index.php?title=Representing_ghost_data)
   to mark ghost cells and blanked cells

3. save space: the arrays for storing blanking are not needed anymore

Note that ghosts and blanking exists for both cells and points. Simply
replace cell with point to get the corresponding description for point
ghosts and blanking.

# Changes overview

To achieve our goals we made the following changes:

1. Previously, ghost cells were marked in a `unsigned char`
   attribute array called "`vtkGhostLevels`". For each cell, the
   ghost level was stored at the corresponding cell id. Now, there is
   no distinction between ghost levels. Cells at any ghost level, are
   marked by setting `vtkDataSetAttributes::DUPLICATECELL` bit at
   the corresponding cell id, in the `unsigned char` attribute
   array called `vtkDataSetAttributes::GhostArrayName()`
   ("`vtkGhostType`").

2. Previously, filters striped all ghost cells they requested from
   upstream before finalizing the output. This is no longer done. The
   user can remove all ghost cells at the end of pipeline processing,
   if needed. Note that ghost cells are not shown in the render
   window, and only consume a small amount of memory compared with the
   whole dataset which means that removing them is often not
   necessary.

3. `vtkUniformGrid` and `vtkStructuredGrid` previously
   supported blanking through member arrays `CellVisibility` and
   `PointVisibility`. These arrays are removed and the blanking
   functionality is supported by setting
   `vtkDataSetAttributes::HIDDENCELL` bit at the corresponding
   cell id in the "`vtkGhostType`" attribute array.

4. We increase file version for VTK Legacy files (see VTK/IO/Legacy)
   to 4.0 (from 3.0). We increase file version for VTK XML files (see
   VTK/IO/XML) to 2.0 (from 0.1 for files using UInt32 header type and
   from 1.0 for files using UInt64 header type). We increase these
   versions because ghost cells are now stored in a file using the new
   `vtkGhostType` format described in the previous section.  New
   readers reading old files convert a `vtkGhostLevels` attribute
   array to a `vtkGhostType` array. This preserves ghost cells
   written using old readers.

# Bits used in the ghost type array

We use the following bits to store information about each cell in the
dataset. These bits are
[compatible](http://www.visitusers.org/index.php?title=Representing_ghost_data)
with Visit.

`vtkDataSetAttribute::DUPLICATECELL` specifies that this cell is
present on multiple processors. This is a ghost cell. This cell is not
rendered. It is present only to help obtain correct results when
processing only a subset of the original data. Attributes associated
with these cells are valid, so they can be used in certain statistical
operations such as min/max. Ghost cells should not be used in
operations such as average because this would result counting the same
cell several times. A similar description applies to
`vtkDataSetAttribute::DUPLICATEPOINT`

`vtkDataSetAttribute::REFINEDCELL` specifies that other cells are
present that refine this cell. Because the coarser grid is often a
structured grid, it is difficult to remove cells that are further
refined. Instead, this bit is used to mark this kind of cells. Values
associated with this cell may be used in interpolation. Note that
there is no vtkDataSetAttribute::REFINEDPOINT.  For more information
about AMR datasets in VTK see
[Visualization & Analysis of AMR Datasets](http://www.kitware.com/source/home/post/32) in The Source.

`vtkDataSetAttribute::HIDDENCELL` specifies that this cell is not
part of the model, it is only used to maintain the connectivity of the
grid. This is a blank cell. It is not rendered and any values
associated with it are ignored. A similar description applies to
`vtkDataSetAttribute::HIDDENPOINT`

Other bits specified by VisIt are not used in VTK.

# API Changes

To test if a cell is a ghost cell, previously, we used
`grid->GetCellData()->GetArray("vtkGhostLevels")->GetValue(cellId) >
0`. This is because we stored ghost levels in the ghost array. Now
we use `grid->GetCellGhostArray()->GetValue(cellId) &
vtkDataSetAttributes::DUPLICATECELL`.

To specify that a cell is a ghost cell, instead of
`grid->GetCellData()->GetArray("vtkGhostLevels")->SetValue(cellId,
ghostLevel)`, use: ` vtkUnsignedCharArray* ghosts =
grid->GetCellGhostArray(); ghosts->SetValue(cellId,
ghosts->GetValue(cellId) | vtkDataSetAttributes::DUPLICATECELL); `
Note that we use a 'or' operation to preserve other bits that might be
set for the cell.

To create a new ghost array, instead of
`vtkDataSet::GenerateGhostLevelArray`, use
`vtkDataSet::GenerateGhostArray`. We changed the name because there
are no ghost levels in the new ghost array.

To test if there are any ghost cells, instead of
`grid->GetCellData()->GetArray("vtkGhostLevels") != NULL`, use
`grid->HasAnyGhostCells()`. Make similar changes to test if there
are any blank cells. We made this change because previously a non-NULL
ghost array meant that there are ghost cells, now this means that
there are blank cells or ghost cells.

To get a pointer to the ghost array, instead of
`grid->GetCellData()->GetArray("vtkGhostLevels")`, use
`grid->GetCellGhostArray()`. This new function avoids O(N) string
comparisons by caching the ghost array pointer.

We remove a ghostLevel parameter from
`vtkPolyData::RemoveGhostCells`,
`vtkUnstructuredGrid::RemoveGhostCells`,
`vtkGlyph3D::Execute`,
`vtkDataSetSurfaceFilter::UnstructuredGridExecute`. This is
because we no longer remove ghost levels requested by a filter after
the filter finishes executing.

We remove `GetCellVisibilityArray` from `vtkStructuredGrid`
and `vtkUniformGrid`. Use `GetCellGhostArray` instead and use
`vtkDataSetAttributes::HIDDENCELL` bit to set or test if a cell is
blanked.

We add an extra parameter to `vtkDataReader::ReadFieldData`,
`vtkXMLDataReader::ReadArrayValues`,
`vtkXMLStructuredDataReader::ReadSubExtent` which specifies if we
read cell or point data. This is needed so that we can use the proper
bits when converting ghost levels.

We remove `vtkStructuredGridWriter:::WriteBlanking` as blanking is
now written when saving the `vtkGhostType` array.

# VTK XML file version update (4/16/2015)

Users with an older VTK won't be able to read VTK XML files generated
with a new VTK containing the ghost changes described even if those
files do not contain ghost or blanking cells. This is because we
increment VTK XML file version.

To fix this, we use the previous file version for VTK XML files (0.1
for files using UInt32 header type and 1.0 for files using UInt64
header type) unless data is unstructured or structured grid and there
is a vtkGhostType array.
