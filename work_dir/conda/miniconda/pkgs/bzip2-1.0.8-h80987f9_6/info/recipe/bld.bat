@echo on

REM The bzip2 executable uses the environment variables BZIP2 and BZIP to initialise its ArgList
REM conda sets these values from conda_build_config.yaml and bzip2 tries to open a file called "1.0"
set BZIP2=
set BZIP=

REM Build step
nmake -f makefile.msc
if errorlevel 1 exit 1

REM Install step
copy bzlib.h %LIBRARY_INC% || exit 1
copy libbz2_static.lib %LIBRARY_LIB% || exit 1
REM Some packages expect 'bzip2.lib', so make another copy
copy libbz2_static.lib %LIBRARY_LIB%\bzip2_static.lib || exit 1

copy libbz2.lib %LIBRARY_LIB% || exit 1
REM Some packages expect 'bzip2.lib', so make copies
copy libbz2.lib %LIBRARY_LIB%\bzip2.lib || exit 1
copy libbz2.exp %LIBRARY_LIB%\libbz2.exp || exit 1
copy libbz2.def %LIBRARY_LIB%\libbz2.def || exit 1

copy libbz2.dll %LIBRARY_BIN% || exit 1
REM Some packages expect 'bzip2.dll', so make copies
copy libbz2.dll %LIBRARY_BIN%\bzip2.dll || exit 1

REM Copy also uppercased variant of the dll
copy LIBBZ2.dll %LIBRARY_BIN%\LIBBZ2.dll || exit 1

REM Copy exe files
copy *.exe %LIBRARY_BIN% || exit 1
