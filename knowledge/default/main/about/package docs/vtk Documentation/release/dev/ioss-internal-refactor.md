## IOSS reader internals refactored

The IOSS reader's implementation is quite large and owned a private
"Internals" class that is quite large. This has been split into a
separate header (1) to allow subclassing the reader and (2) to keep
file sizes lower.

The IOSS reader is being subclassed to provide a version that will
produce vtkCellGrid instances (instead of vtkUnstructuredGrid
instances) for each block/set.
