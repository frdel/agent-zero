Fix issues with VTK / VTK-m array conversion

Changed the VTK to VTK-m array conversion routines to use
`ArrayHandleRuntimeVec` and `ArrayHandleRecombineVec`. These are new
features of VTK-m that allow you to specify an array with the tuple size
specified at runtime. This change improves several specific things.

* Fixes a bug when importing an array of "odd" tuple size (not 1, 2,
  3, 4, 6, or 9). It was creating arrays of size one less than the
  actual size.
* Avoids using `ArrayHandleGroupVecVariable`, which is supported by
  fewer VTK-m filters.
* The VTK-m `ArrayHandle` now manages a reference back to the VTK
  array, so the `ArrayHandle` will continue to work even if the
  original VTK array is "deleted." This makes the code safer.
* Unifies the implementation of the array conversion among number of
  components to avoid issues with surprise tuple sizes.
* Revamped vtkmDataArray to support general array types. This makes
  it more efficient to pass data from VTK-m to VTK when unified
  memory is not available.
