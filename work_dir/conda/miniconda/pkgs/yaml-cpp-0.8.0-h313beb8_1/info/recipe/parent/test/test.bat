:: cmd
echo on

:: Enter test directory.
cd test
if errorlevel 1 exit 1

:: Isolate the build.
mkdir build
cd build
if errorlevel 1 exit 1

:: Generate the build files, compile the test, and run it.
cmake .. -GNinja -DCMAKE_PREFIX_PATH=$PREFIX
ninja
if errorlevel 1 exit 1
test.exe
if errorlevel 1 exit 1


:: Perform additional testing.
if not exist %LIBRARY_BIN%\yaml-cpp.dll exit 1

:: Success
exit 0
