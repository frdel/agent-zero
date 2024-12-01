
cd win32


cscript configure.js compiler=msvc iconv=yes icu=no zlib=yes lzma=no python=no ^
                     threads=ctls ^
                     prefix=%LIBRARY_PREFIX% ^
                     include=%LIBRARY_INC% ^
                     lib=%LIBRARY_LIB%

if errorlevel 1 exit 1

nmake /f Makefile.msvc
if errorlevel 1 exit 1

nmake /f Makefile.msvc install
if errorlevel 1 exit 1

del %LIBRARY_PREFIX%\bin\test*.exe || exit 1
del %LIBRARY_PREFIX%\bin\runsuite.exe || exit 1
del %LIBRARY_PREFIX%\bin\runtest.exe || exit 1
