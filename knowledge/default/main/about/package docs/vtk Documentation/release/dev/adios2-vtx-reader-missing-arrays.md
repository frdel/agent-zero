Add protection for missing arrays in ADIOS2 VTX reader

Previously, when the ADIOS2 VTX reader read in most data arrays from the
ADIOS2 file, it would silently leave a null array if that array did not
exist. This opened up the likely consequence of the program later
crashing when the reader attempted to use this array.

Instead, the reader now reports an error when an array it attempts to
read in is missing. This prevents subsequent problems.
