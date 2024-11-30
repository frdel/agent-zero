## Fix cell data with time in ADIOS2 VTX reader

The ADIOS2 VTX reader supports cell data. However, the previous
implementation of the reader hard-coded the cell data to be static
so that only the first time step was read. The new implementation
checks the time dimension for cell (and point) fields and will
automatically read a field over time if available.
