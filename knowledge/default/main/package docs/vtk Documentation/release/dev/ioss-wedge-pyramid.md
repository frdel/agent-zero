## Fix IOSS reader handling higher order elements

The 21-node wedge and 18-node pyramid were not properly read from IOSS files;
the wedge was incorrectly demoted to a linear wedge while the pyramid was
not read at all. Furthermore, no node re-ordering was performed for the
21-node wedge even though it is required.

The wedge is now properly supported.
The 18-node pyramid is demoted to a 13-node pyramid, since VTK only supports
5-, 12-, 13-, and 19-node pyramids. Promotion to a 19-node pyramid is not
feasible given the way the IOSS reader is structured.
