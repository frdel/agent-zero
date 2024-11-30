## Change to the Python `char` wrapping

If a VTK method parameter is type `char`, you can pass any python string `s`
where `ord(s) < 256`, instead of being restricted to ASCII characters.  If a
VTK method returns `char`, then return value is always a python `str` with
a length of 1, with the null char being `'\x00'`.  Previously, a `char` value
of zero would be returned as `''` (empty string), and calling `ord()` on an
empty string raises an exception.  Now, calling `ord()` on the returned value
will never raise an exception.
