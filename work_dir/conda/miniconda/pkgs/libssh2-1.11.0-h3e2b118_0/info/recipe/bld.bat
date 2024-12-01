set PATH=%PREFIX%\cmake-bin\bin;%PATH%

set CFLAGS=
set CXXFLAGS=

mkdir build
pushd build
  cmake .. -GNinja                           ^
    -DCMAKE_INSTALL_PREFIX=%LIBRARY_PREFIX%  ^
    -DCMAKE_BUILD_TYPE=Release               ^
    -DBUILD_SHARED_LIBS=ON                   ^
    -DBUILD_STATIC_LIBS=OFF                  ^
    -DCMAKE_INSTALL_PREFIX=%LIBRARY_PREFIX%  ^
    -DCMAKE_PREFIX_PATH=%LIBRARY_PREFIX%     ^
    -DENABLE_ZLIB_COMPRESSION=ON             ^
    -DCRYPTO_BACKEND=OpenSSL                 ^
    -DBUILD_EXAMPLES=OFF                     ^
    -DBUILD_TESTING=ON                       ^
    -DRUN_DOCKER_TESTS=OFF                   ^
    -DRUN_SSHD_TESTS=OFF                     ^
    %CMAKE_ARGS%

  ninja -j%CPU_COUNT%
  IF %ERRORLEVEL% NEQ 0 exit 1
  REM Skip Docker and SSHD tests (see above) because they involve external dependencies
  ctest --output-on-failure
  IF %ERRORLEVEL% NEQ 0 exit 1
  ninja install
  IF %ERRORLEVEL% NEQ 0 exit 1
popd
