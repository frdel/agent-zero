## Cell Grid Data-object Improvements

vtkCellGrid is a new subclass of vtkDataObject aimed at supporting
data which breaks the assumptions vtkDataSet makes (such as
spatially-varying attributes requiring multiple arrays to compute
interpolated values;
cell-data values representing functions producing a constant value
over the entire cell;
or that cell shapes are defined by corner points that are exactly interpolated).
The cell-grid class makes very few assumptions about your data;
instead, it is a container for arrays related to your data and you
must register instances of subclasses of vtkCellGridResponder to
respond to the particular queries (subclasses of vtkCellGridQuery)
you wish to support.

### Discontinuous (and Continuous) Galerkin Cells

This release includes generalizations and extensions to support
H(Curl), H(Div), and H(Grad) function spaces.
It also contains classes that use this new functionality to
implement fixed-topology cells which support these function spaces.
The cell classes all inherit `vtkDGCell` (named as they are
intended to support discontinuous Galerkin finite elements; however,
your solution fields do not need to be computed with a Galerkin
solver to make use of them).

Of particular note is that these cells allow the geometric shape
and other cell-attributes to have different polynomial interpolation
orders (i.e., non-isoparametric cells are supported).
For example, this image

![cell-grid-non-isoparametric](cell-grid-non-isoparametric.png)

shows two linear hexahedral cells colored by a quadratic attribute.
Not only do the colors vary nonlinearly across the faces of the cells,
but there is a discontinuity in the color-mapped field at the boundary
that cannot be modeled by `vtkDataSet` and its subclasses.

Finally, as this section's title hints, even though the cell classes
are named `DG`, they also support continuous (`CG`) cells where each
degree of freedom is referenced by a connectivity entry.

### Multi-pass Cell Grid Queries

This release, vtkCellGridQuery has been modified to allow for multiple
passes. A new virtual method `IsAnotherPassRequired()` is provided;
by default it returns false so existing query classes do not need
to be modified. Override it if your algorithm needs multiple passes,
but be aware it must eventually return false for the algorithm to
terminate.

Another virtual method, `StartPass()`, is called at the beginning
of each pass and you may override it to update the query's state
as needed. This method exists in addition to the `Initialize()`
and `Finalize()` methods already invoked at the beginning and end
of the entire query.

### New Queries and Responders

The following subclasses of vtkCellGridQuery are now available.

+ vtkCellGridBoundsQuery – compute the spatial (3D) bounds of a cell grid.
+ vtkCellGridEvaluator – classify and evaluate cell attributes of a cell grid
  at a set of input points.
+ vtkCellGridRangeQuery – compute the range of a cell attribute.
+ vtkCellGridSidesQuery – compute the number of occurrences of cell boundaries
  of any dimension.
+ vtkCellGridElevationQuery – add an "elevation" attribute to an existing cell grid.
+ vtkUnstructuredGridToCellGrid::TranscribeQuery – transform an unstructured grid
  (potentially with special markup) into a cell grid.
  Note that this query is an implementation detail inside a subclass of vtkAlgorithm.
+ vtkCellGridRenderRequest – render a cell grid.

Each query class has a matching responder to support continuous and discontinuous
Galerkin (CG and DG) cells that support H(Curl), H(Div), and H(Grad) function spaces
for their cell attributes.
Only H(Grad) interpolation is supported for a grid's "shape" attribute (the mapping from
reference elements into world coordinates).

### Filters based on Queries

Several of the queries above are used to implement
subclasses of vtkAlgorithm which accept cell grids.
Other algorithm classes contain their own query classes
nested into the algorithm.

+ vtkCellGridComputeSides – compute the external boundaries of cells using vtkCellGridSidesQuery.
+ vtkCellGridElevation – add a new cell attribute to an existing cell grid using vtkCellGridElevationQuery.
+ vtkUnstructuredGridToCellGrid – convert an unstructured grid into a cell grid using its internal TranscribeQuery.
+ vtkCellGridCellCenters – place a vertex cell at the parametric center of each input cell.
+ vtkCellGridCellSource – generate a single cell of the requested type, optionally with cell attributes.
+ vtkLegacyCellGridWriter – write cell-grid data in VTK's "legacy" format (by wrapping JSON into a legacy header).
+ vtkLegacyCellGridReader – read cell-grid data from a "legacy"-formatted file.
+ vtkCellGridToUnstructuredGrid – convert to an approximating unstructured grid;
  currently, all cell-attributes are converted to point-data and the output will have linear
  geometry even if the source uses quadratic or higher order interpolation.
+ vtkPassSelectedArrays – this pre-existing filter now handles cell-grid data;
  instead of named arrays being passed/omitted, entire cell-attributes (with all of their arrays)
  are passed/omitted.
+ vtkCellGridTransform – apply a linear transform to the shape attribute of a cell-grid.
+ vtkCellGridWarp – add a scaled version of a cell-attribute to the shape attribute of a cell-grid.
+ vtkIOSSCellGridReader – read exodus-formatted files as cell-grids rather than unstructured grids.

### Attribute Calculators

Just as cell grids can be asked for responders to different types of queries,
we have added new functionality to deal with cell attributes.
This way, a query responder can ask a separate object to perform interpolation,
integration, or other calculations involving cell attributes.
These objects all inherit the base class vtkCellAttributeCalculator.

If a responder does not need special information about a cell-attribute,
it can delegate calculations to an attribute calculator.
Each subclass of vtkCellAttributeCalculator provides its own custom
API for performing its calculations.

For example, responders to the vtkCellGridEvaluator query need to classify
points as inside cells, evaluate the parametric coordinates at points classified
as interior to a cell, and interpolate an attribute value at the parametric
coordinates.
Each of these tasks requires knowledge of either the shape attribute or another
cell-attribute defined over the grid.
While the responder knows how to handle specific types of cells,
its work does not require it to know how to handle interpolation in every function
space supported by every cell-attribute.
Therefore, it asks for an attribute calculator specific to

+ the work it needs performed (interpolation of the cell-attribute),
+ the current cell type, and
+ the relevant cell-attribute,

rather than hardwiring support for a fixed set of function spaces.

The vtkCellGridResponders class – in addition to holding a registry of responders
for cell types to different query types – now also holds a registry of these
calculator classes that can perform calculations on cell-attributes of different
types (i.e., different function spaces).
This allows support for new function spaces to be added to existing algorithm
implementations without changes.

In the next section below, we discuss the first cell-attribute calculator
subclass provided by VTK.

### Interpolation Calculator

We now provide a base class, vtkInterpolateCalculator, for evaluating cell attributes
and their derivatives at one or more points inside cells.
Similar to the query/responder pattern above, you may register subclasses to handle
not just specific types of cells but also specific function spaces defined on those
cells.

An implementation (via a subclass) is provided for CG/DG cells that works with
H(Curl), H(Div), and H(Grad) function spaces.

### Rendering

The rendering query for cell grids has been refactored to support novel function
spaces and also to make prototyping and debugging simpler;
a base `vtkDrawTexturedElements` class is provided that binds a user-specified set of
arrays to OpenGL texture objects and calls `glDrawElementsInstanced()` with the number
of elements and instances you specify. You can also set the shape of elements rendered
(i.e., lines, triangles, strips, etc.).
Thus, given

+ a set of vtkDataArrays and names for their samplers;
+ a set of shader programs (vertex, geometry, and fragment);
+ an element shape;
+ the number of elements; and
+ the number of instances of the elements above;

the array renderer will use the arrays however your shaders choose to draw data.

The vtkOpenGLCellGridMapper uses a vtkCellGridRenderRequest to find
responders that can render input cell grids and the DG responder configures an
array renderer to draw its cells to a framebuffer.

## Example Application

The `Examples/GUI/Qt/CellGridSource` directory contains an example application
using the vtkCellGridCellSource filter to construct a single cell so you can
explore the way arrays in different array-groups are used to specify cell-grids.
It has an editable spreadsheet view so you can change the coefficients used to
define the cell's attributes (including its shape).
