:: cmd
set LIB=%LIBRARY_LIB%;%LIB%
set LIBPATH=%LIBRARY_LIB%;%LIBPATH%
set INCLUDE=%LIBRARY_INC%;%INCLUDE%;%RECIPE_DIR%

:: Isolate the build.
mkdir Build
cd Build
if errorlevel 1 exit /b 1


:: Generate the build files.
echo "Generating the build files."
cmake .. %CMAKE_ARGS% ^
      -G"NMake Makefiles" ^
      -DCMAKE_PREFIX_PATH=%LIBRARY_PREFIX% ^
      -DCMAKE_INSTALL_PREFIX=%LIBRARY_PREFIX% ^
      -DCMAKE_BUILD_TYPE=Release
if errorlevel 1 exit 1


:: Build.
echo "Building..."
nmake
if errorlevel 1 exit /b 1


:: Perforem tests.
echo "Testing..."
ctest -VV --output-on-failure


:: Install.
echo "Installing..."
nmake install
if errorlevel 1 exit /b 1


:: Some OSS libraries are happier if z.lib exists, even though it's not typical on Windows.
copy %LIBRARY_LIB%\zlib.lib %LIBRARY_LIB%\z.lib || exit 1

:: Qt in particular goes looking for this one (as of 4.8.7).
copy %LIBRARY_LIB%\zlib.lib %LIBRARY_LIB%\zdll.lib || exit 1

:: Copy license file to the source directory so conda-build can find it.
copy %RECIPE_DIR%\license.txt %SRC_DIR%\license.txt || exit 1

:: python>=3.10 depend on this being at %PREFIX%
copy %LIBRARY_BIN%\zlib.dll %PREFIX%\zlib.dll || exit 1


:: Error free exit.
echo "Error free exit!"
exit 0
