set CXXFLAGS=
set CFLAGS=

mkdir build
pushd build

cmake -GNinja -D CMAKE_INSTALL_PREFIX=%LIBRARY_PREFIX% -D CMAKE_BUILD_TYPE=Release ..
if errorlevel 1 exit 1

ninja
if errorlevel 1 exit 1

:: Test.
ctest -C Release
if errorlevel 1 exit 1

:: Install.
ninja install
if errorlevel 1 exit 1
