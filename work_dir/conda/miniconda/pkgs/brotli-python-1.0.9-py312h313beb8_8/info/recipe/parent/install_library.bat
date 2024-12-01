echo "--------------------------"
echo "Installing brotli binaries"

set CMAKE_CONFIG=Release
pushd build_shared_%CMAKE_CONFIG%

echo on

cmake --build . --target install
if errorlevel 1 exit 1

if [%PKG_NAME%] == [libbrotlicommon] (
  del %LIBRARY_PREFIX%\bin\brotli.exe
  if errorlevel 1 exit 1
  del %LIBRARY_PREFIX%\lib\brotlidec.lib
  if errorlevel 1 exit 1
  del %LIBRARY_PREFIX%\bin\brotlidec.dll
  if errorlevel 1 exit 1
  del %LIBRARY_PREFIX%\lib\pkgconfig\libbrotlidec.pc
  if errorlevel 1 exit 1
  del %LIBRARY_PREFIX%\lib\brotlienc.lib
  if errorlevel 1 exit 1
  del %LIBRARY_PREFIX%\bin\brotlienc.dll
  if errorlevel 1 exit 1
  del %LIBRARY_PREFIX%\lib\pkgconfig\libbrotlienc.pc
  if errorlevel 1 exit 1
)

if [%PKG_NAME%] == [libbrotlienc] (
  del %LIBRARY_PREFIX%\bin\brotli.exe
  if errorlevel 1 exit 1
  del %LIBRARY_PREFIX%\lib\brotlidec.lib
  if errorlevel 1 exit 1
  del %LIBRARY_PREFIX%\bin\brotlidec.dll
  if errorlevel 1 exit 1
  del %LIBRARY_PREFIX%\lib\pkgconfig\libbrotlidec.pc
  if errorlevel 1 exit 1
)

if [%PKG_NAME%] == [libbrotlidec] (
  del %LIBRARY_PREFIX%\bin\brotli.exe
  if errorlevel 1 exit 1
  del %LIBRARY_PREFIX%\lib\brotlienc.lib
  if errorlevel 1 exit 1
  del %LIBRARY_PREFIX%\bin\brotlienc.dll
  if errorlevel 1 exit 1
  del %LIBRARY_PREFIX%\lib\pkgconfig\libbrotlienc.pc
  if errorlevel 1 exit 1
)

if NOT [%PKG_NAME%] == [brotli] (
  rd /s /q %LIBRARY_INC%\brotli
  if errorlevel 1 exit 1
)
