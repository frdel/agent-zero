SETLOCAL EnableDelayedExpansion
cd source

:: Remove all instances of /W4 from configure.
:: They get passed to the linker and confuse it.
:: Given that we aren't interested in warnings anyway
:: remove it. I could have used a patch but this seemed
:: more 'upgrade friendly'
sed "s~ /W4~~g" configure > configure.new
move configure.new configure

:: This seems to be required - not sure why but
:: rc.exe gets confused with the '/' form of slashes
set MSYS_RC_MODE=1

:: 32-bit and VS2015 ends in failure:
:: uconv.o : MSIL .netmodule or module compiled with /GL found; restarting link with /LTCG; add /LTCG to the link command line to improve linker performance
:: uconv.o : error LNK2001: unresolved external symbol _uconvmsg_dat
:: ../../bin/uconv.exe : fatal error LNK1120: 1 unresolved externals
:: .. without this
if "%ARCH%"=="32" (
  if "%c_compiler%"=="vs2015" (
    set EXTRA_OPTS=--disable-extras
  )
)

:: This directory is needed during the install process but isn't created by the scripts.
mkdir data\out\tmp

set BUILD=x86_64-pc-cygwin
set HOST=x86_64-pc-cygwin
cd ..

copy "%RECIPE_DIR%\build.sh" .
set MSYSTEM=MINGW%ARCH%
set MSYS2_PATH_TYPE=inherit
set CHERE_INVOKING=1
FOR /F "delims=" %%i in ('cygpath.exe -u "%LIBRARY_PREFIX%"') DO set "PREFIX=%%i"

set CC=cl.exe
set CXX=cl.exe

bash -lc "./build.sh"
if errorlevel 1 exit 1

:: The .dlls end up in the wrong place
move %LIBRARY_LIB%\icu*.dll %LIBRARY_BIN%
if errorlevel 1 exit 1
