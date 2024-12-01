if "%ARCH%" == "64" (
  set ARCH="x64"
) else (
  set ARCH="Win32"
)

mkdir buildd
cd buildd
cmake -G "NMake Makefiles" ^
  -D CMAKE_BUILD_TYPE=Release ^
  -D CMAKE_PREFIX_PATH=%LIBRARY_PREFIX% ^
  -D CMAKE_INSTALL_PREFIX:PATH=%LIBRARY_PREFIX% ^
  -D BUILD_SHARED_LIBS:BOOL=ON ^
  -D VERSION=%PKG_VERSION% ^
  ..

echo "configured ..."

cmake --build . --config Release

echo "built ..."

cmake --build . --target install --config Release

if errorlevel 1 exit 1

copy %LIBRARY_LIB%\ffi.lib %LIBRARY_LIB%\libffi.lib
copy %LIBRARY_LIB%\ffi.lib %LIBRARY_LIB%\libffi.dll.lib
copy %LIBRARY_PREFIX%\bin\ffi.dll %LIBRARY_PREFIX%\bin\ffi-8.dll
:: ffi-8 is backward compatible to ffi-7
copy %LIBRARY_PREFIX%\bin\ffi.dll %LIBRARY_PREFIX%\bin\ffi-7.dll

exit 0

