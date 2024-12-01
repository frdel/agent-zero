:: cmd

:: Isolate the build.
mkdir build_shared
cd build_shared
if errorlevel 1 exit 1

:: Generate the build files.
cmake .. -G"Ninja" ^
    -DYAML_CPP_BUILD_TESTS=ON ^
    -DYAML_BUILD_SHARED_LIBS=ON ^
    -DCMAKE_BUILD_TYPE=Release ^
    -DCMAKE_PREFIX_PATH=%LIBRARY_PREFIX% ^
    -DCMAKE_INSTALL_PREFIX=%LIBRARY_PREFIX% ^
    -DYAML_CPP_INSTALL=ON

if errorlevel 1 exit 1

:: Build and install.
ninja install
if errorlevel 1 exit 1


:: Call author's tests.
test\yaml-cpp-tests
if errorlevel 1 exit 1

:: Success!
exit 0
