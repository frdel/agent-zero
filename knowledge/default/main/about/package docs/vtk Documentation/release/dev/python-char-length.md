## C++ char parameters only take Python chars

Previously Python strings like `''` and `'x\0'` or even `'x\0y'` would be
accepted by VTK methods requiring a C++ `char` parameter.  Now, only strings
of length 1 are accepted.  Unicode characters are allowed as long as the
code value is 255 or less, otherwise ValueError is raised.  To pass a number
via a `char` parameter, use `chr(n)`.
