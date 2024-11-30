## Add Windows utf-8 support to more IO classes

This allows the following classes to use Unicode paths on Windows, even
when the system code page is not set to UTF8:

vtkDirectory, vtkTIFFReader, vtkTIFFWriter, vtkTecplotReader,
vtkNIFTIImageReader, and vtkNIFTIImageWriter.
