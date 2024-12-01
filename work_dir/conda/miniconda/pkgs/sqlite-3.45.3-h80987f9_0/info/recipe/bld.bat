if "%ARCH%"=="32" (
set PLATFORM=x86
) else (
set PLATFORM=x64
)

:: build the shell
cl ^
    /DSQLITE_ENABLE_RTREE ^
    /DSQLITE_ENABLE_GEOPOLY ^
    /DSQLITE_ENABLE_COLUMN_METADATA=1 ^
    /DSQLITE_MAX_VARIABLE_NUMBER=250000 ^
    /DSQLITE_ENABLE_FTS5 ^
    shell.c sqlite3.c -Fesqlite3.exe ^
    /DSQLITE_EXPORTS

:: build the dll
cl ^
    /DSQLITE_ENABLE_RTREE ^
    /DSQLITE_ENABLE_GEOPOLY ^
    /DSQLITE_ENABLE_COLUMN_METADATA=1 ^
    /DSQLITE_MAX_VARIABLE_NUMBER=250000 ^
    /DSQLITE_ENABLE_JSON1 ^
    /DSQLITE_ENABLE_FTS5 ^
    sqlite3.c -link -dll -out:sqlite3.dll

COPY sqlite3.exe  %LIBRARY_BIN% || exit 1
COPY sqlite3.dll  %LIBRARY_BIN% || exit 1
COPY sqlite3.lib  %LIBRARY_LIB% || exit 1
COPY sqlite3.h    %LIBRARY_INC% || exit 1
COPY sqlite3ext.h %LIBRARY_INC% || exit 1
