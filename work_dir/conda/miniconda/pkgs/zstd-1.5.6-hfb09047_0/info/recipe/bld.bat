pushd "%SRC_DIR%"\build\cmake
cmake -GNinja ^
    -DCMAKE_BUILD_TYPE=Release ^
    -DCMAKE_INSTALL_PREFIX="%LIBRARY_PREFIX%" ^
    -DCMAKE_INSTALL_LIBDIR="lib" ^
    -DCMAKE_PREFIX_PATH="%LIBRARY_PREFIX%" ^
    -DZSTD_ZLIB_SUPPORT=ON ^
    -DZSTD_LZ4_SUPPORT=ON ^
    -DZSTD_BUILD_SHARED=ON
if errorlevel 1 exit 1
cmake --build . --target install
if errorlevel 1 exit 1
copy lib\zstd.dll  %PREFIX%\Library\bin\zstd.dll
if errorlevel 1 exit 1
copy %PREFIX%\Library\bin\zstd.dll %PREFIX%\Library\bin\libzstd.dll
if errorlevel 1 exit 1
copy %PREFIX%\Library\lib\zstd.lib %PREFIX%\Library\lib\libzstd.lib
if errorlevel 1 exit 1
copy %PREFIX%\Library\lib\zstd_static.lib %PREFIX%\Library\lib\libzstd_static.lib
if errorlevel 1 exit 1
