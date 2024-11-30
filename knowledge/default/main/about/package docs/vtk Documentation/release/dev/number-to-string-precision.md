## vtkNumberToString : move class and add options to specify notation and precision

`vtkNumberToString` now lives in Common/Core instead of IO/Core,
to make the class more central and accessible to any VTK class needing to properly format numbers.

`vtkNumberToString` has been enhanced to support printing formatted string from double and float values.
A new method `SetNotation` can be used to specify whether the output should use scientific, fixed-point notation,
or a mix of both depending on the value's exponent (previous behavior, still default).

In addition, one can now specify the number of digits to print after the decimal for both scientific and fixed-point notation using `SetPrecision`.
