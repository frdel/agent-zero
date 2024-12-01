mkdir build
cd build

cmake -G "Ninja" ^
      -D CMAKE_INSTALL_PREFIX=%LIBRARY_PREFIX% ^
      -D CMAKE_PREFIX_PATH=%LIBRARY_PREFIX% ^
      -D CMAKE_VERBOSE_MAKEFILE=ON ^
      -D ENABLE_CONDA=ON ^
      -D MULTI_SEMANTICS=ON ^
      -D WITHOUT_COOKIEOPEN=ON ^
      -D CMAKE_BUILD_TYPE=Release ^
      -D CMAKE_MSVC_RUNTIME_LIBRARY="MultiThreadedDLL" ^
      -D DISABLE_SHARED=OFF ^
      -D ENABLE_STATIC=OFF ^
      -D ENABLE_PCRE2=ON ^
      ..
if errorlevel 1 exit 1

ninja
if errorlevel 1 exit 1

cd ..
mkdir static_build
cd static_build

cmake -G "Ninja" ^
      -D CMAKE_INSTALL_PREFIX=%LIBRARY_PREFIX% ^
      -D CMAKE_PREFIX_PATH=%LIBRARY_PREFIX% ^
      -D CMAKE_VERBOSE_MAKEFILE=ON ^
      -D ENABLE_CONDA=ON ^
      -D MULTI_SEMANTICS=ON ^
      -D WITHOUT_COOKIEOPEN=ON ^
      -D CMAKE_BUILD_TYPE=Release ^
      -D CMAKE_MSVC_RUNTIME_LIBRARY="MultiThreadedDLL" ^
      -D ENABLE_STATIC=ON ^
      -D DISABLE_SHARED=ON ^
      -D ENABLE_PCRE2=ON ^
      ..

if errorlevel 1 exit 1

ninja
if errorlevel 1 exit 1
