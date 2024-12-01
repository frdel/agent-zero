@REM Use the MSVC sln to build static lib and dll
msbuild ^
  /p:Platform=%PLATFORM% ^
  /p:Configuration=Release ^
  /p:AdditionalIncludeDirectories=%LIBRARY_INC% ^
  /p:AdditionalDependencies=/LIBPATH:%LIBRARY_LIB% ^
  /p:WindowsTargetPlatformVersion=10.0.17763.0 ^
  windows\%c_compiler%\xz_win.sln

COPY windows\%c_compiler%\Release\x64\liblzma\liblzma.lib %LIBRARY_LIB%\liblzma_static.lib
COPY windows\%c_compiler%\Release\x64\liblzma_dll\liblzma.lib %LIBRARY_LIB%\liblzma.lib
COPY windows\%c_compiler%\Release\x64\liblzma_dll\liblzma.dll %LIBRARY_PREFIX%\bin\liblzma.dll

@REM Use min-gw to build command line tools
set MSYSTEM=MINGW%ARCH%
set MSYS2_PATH_TYPE=inherit
set CHERE_INVOKING=1

@REM No longer want to use cl.exe
set CC=

set "saved_recipe_dir=%RECIPE_DIR%"
FOR /F "delims=" %%i IN ('cygpath.exe -u -p "%PATH%"') DO set "PATH_OVERRIDE=%%i"
FOR /F "delims=" %%i IN ('cygpath.exe -u "%BUILD_PREFIX%"') DO set "BUILD_PREFIX=%%i"
FOR /F "delims=" %%i IN ('cygpath.exe -m "%LIBRARY_PREFIX%"') DO set "LIBRARY_PREFIX_M=%%i"
FOR /F "delims=" %%i IN ('cygpath.exe -u "%LIBRARY_PREFIX%"') DO set "LIBRARY_PREFIX_U=%%i"
FOR /F "delims=" %%i IN ('cygpath.exe -u "%PREFIX%"') DO set "PREFIX=%%i"
FOR /F "delims=" %%i IN ('cygpath.exe -u "%RECIPE_DIR%"') DO set "RECIPE_DIR=%%i"
FOR /F "delims=" %%i IN ('cygpath.exe -u "%SP_DIR%"') DO set "SP_DIR=%%i"
FOR /F "delims=" %%i IN ('cygpath.exe -u "%SRC_DIR%"') DO set "SRC_DIR=%%i"
FOR /F "delims=" %%i IN ('cygpath.exe -u "%STDLIB_DIR%"') DO set "STDLIB_DIR=%%i"

bash -lxc %RECIPE_DIR%/bld_win.sh
if %errorlevel% neq 0 exit /b %errorlevel%
exit /b 0s
