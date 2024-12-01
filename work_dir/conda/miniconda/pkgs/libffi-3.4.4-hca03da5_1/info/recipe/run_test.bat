if not exist %LIBRARY_PREFIX%/bin/ffi-7.dll exit /b 1
if not exist %LIBRARY_PREFIX%/lib/libffi.lib exit /b 1
if not exist %LIBRARY_PREFIX%/lib/ffi.lib exit /b 1
if not exist %LIBRARY_PREFIX%/lib/pkgconfig/libffi.pc exit /b 1
if not exist %LIBRARY_PREFIX%/include/ffi.h exit /b 1
if not exist %LIBRARY_PREFIX%/include/ffitarget.h exit /b 1
echo "platform name"
echo %SUBDIR%
if %SUBDIR%==win-64 (llvm-nm %LIBRARY_PREFIX%/lib/libffi.lib | grep "__imp_ffi_type_void" ) else (llvm-nm %LIBRARY_PREFIX%/lib/libffi.lib | grep "__imp__ffi_type_void")
