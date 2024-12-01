@echo on

if not exist %LIBRARY_INC%\bzlib.h exit 1
if not exist %LIBRARY_LIB%\bzip2.lib exit 1
if not exist %LIBRARY_BIN%\bzip2.dll exit 1
if not exist %LIBRARY_LIB%\libbz2.lib exit 1
if not exist %LIBRARY_LIB%\libbz2.exp exit 1
if not exist %LIBRARY_LIB%\libbz2.def exit 1
if not exist %LIBRARY_BIN%\libbz2.dll exit 1
if not exist %LIBRARY_LIB%\bzip2_static.lib exit 1
if not exist %LIBRARY_LIB%\libbz2_static.lib exit 1
if not exist %LIBRARY_BIN%\bzip2.exe exit 1
if not exist %LIBRARY_BIN%\bzip2recover.exe exit 1

echo "hello world" >foo
REM Compress a file
bzip2.exe -zv foo
if errorlevel 1 exit /B 1

REM Decompress the file
bzip2.exe -dc foo.bz2
if errorlevel 1 exit /B 1

REM Compile bz2.c with the import library and /MD option,
REM see https://learn.microsoft.com/en-us/cpp/build/reference/md-mt-ld-use-run-time-library?view=msvc-170#remarks
%CC% /MD /Febz2 bz2.c /I%PREFIX%\Library\include\ /link /LIBPATH:"%PREFIX%\Library\lib" libbz2.lib
if errorlevel 1 exit /B 1

:: Uncomment for the debugging purposes only to check the dynamic libraries
::ldd bz2.exe
::if errorlevel 1 exit /B 1

REM Decompress the file by a compiled executable
bz2 foo.bz2
if errorlevel 1 exit /B 1
