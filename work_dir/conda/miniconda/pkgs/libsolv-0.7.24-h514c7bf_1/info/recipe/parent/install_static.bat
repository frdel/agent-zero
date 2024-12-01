set "CFLAGS= -MD"
echo %CFLAGS%

set "CXXFLAGS= -MD"
echo %CXXFLAGS%

cd static_build
COPY src\solv_static.lib %LIBRARY_PREFIX%\lib\solv_static.lib
COPY ext\solvext_static.lib %LIBRARY_PREFIX%\lib\solvext_static.lib

if errorlevel 1 exit 1
