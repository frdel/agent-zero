VTK now supports reading and writing cell-grid and composite-cell-grid datasets
via the vtkGenericDataReader/Writer classes; this is required by ParaView in
order to send data over a client-server connection to perform client-side rendering
of (small) server-side data.

Cell-grid data is currently encoded as a block of ASCII JSON data obtained using
the readers and writers in the IOCellGrid module. If this proves inadequate for
client-server communication, the data format may change.
