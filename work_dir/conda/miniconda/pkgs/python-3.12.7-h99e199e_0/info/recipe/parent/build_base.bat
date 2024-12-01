setlocal EnableDelayedExpansion
echo on

:: Compile python, extensions and external libraries
if "%ARCH%"=="64" (
   set PLATFORM=x64
   set VC_PATH=x64
   set BUILD_PATH=amd64
) else (
   set PLATFORM=Win32
   set VC_PATH=x86
   set BUILD_PATH=win32
)

for /F "tokens=1,2 delims=." %%i in ("%PKG_VERSION%") do (
  set "VERNODOTS=%%i%%j"
)

::  Make sure the "python" value in conda_build_config.yaml is up to date.
for /F "tokens=1,2 delims=." %%i in ("%PKG_VERSION%") do (
  if NOT "%PY_VER%"=="%%i.%%j" exit 1
)

for /f "usebackq delims=" %%i in (`conda list -p %PREFIX% sqlite --no-show-channel-urls --json ^| findstr "version"`) do set SQLITE3_VERSION_LINE=%%i
for /f "tokens=2 delims==/ " %%i IN ('echo %SQLITE3_VERSION_LINE%') do (set SQLITE3_VERSION=%%~i)
echo SQLITE3_VERSION detected as %SQLITE3_VERSION%

if "%PY_INTERP_DEBUG%"=="yes" (
  set CONFIG=-d
  set _D=_d
) else (
  set CONFIG=
  set _D=
)


if "%DEBUG_C%"=="yes" (
  set PGO=
) else (
  set PGO=--pgo
)

:: AP doesn't support PGO atm?
set PGO=

cd PCbuild

:: Twice because:
:: error : importlib_zipimport.h updated. You will need to rebuild pythoncore to see the changes.
call build.bat %PGO% %CONFIG% -m -e -v -p %PLATFORM%
call build.bat %PGO% %CONFIG% -m -e -v -p %PLATFORM%
if errorlevel 1 exit 1
cd ..

:: Populate the root package directory
for %%x in (python%VERNODOTS%%_D%.dll python3%_D%.dll python%_D%.exe pythonw%_D%.exe) do (
  if exist %SRC_DIR%\PCbuild\%BUILD_PATH%\%%x (
    copy /Y %SRC_DIR%\PCbuild\%BUILD_PATH%\%%x %PREFIX%
  ) else (
    echo "WARNING :: %SRC_DIR%\PCbuild\%BUILD_PATH%\%%x does not exist"
  )
)

for %%x in (python%_D%.pdb python%VERNODOTS%%_D%.pdb pythonw%_D%.pdb) do (
  if exist %SRC_DIR%\PCbuild\%BUILD_PATH%\%%x (
    copy /Y %SRC_DIR%\PCbuild\%BUILD_PATH%\%%x %PREFIX%
  ) else (
    echo "WARNING :: %SRC_DIR%\PCbuild\%BUILD_PATH%\%%x does not exist"
  )
)

copy %SRC_DIR%\LICENSE %PREFIX%\LICENSE_PYTHON.txt
if errorlevel 1 exit 1

:: Populate the DLLs directory
mkdir %PREFIX%\DLLs
xcopy /s /y %SRC_DIR%\PCBuild\%BUILD_PATH%\*.pyd %PREFIX%\DLLs\
if errorlevel 1 exit 1

copy /Y %SRC_DIR%\PC\icons\py.ico %PREFIX%\DLLs\
if errorlevel 1 exit 1
copy /Y %SRC_DIR%\PC\icons\pyc.ico %PREFIX%\DLLs\
if errorlevel 1 exit 1


:: Populate the Tools directory
mkdir %PREFIX%\Tools
xcopy /s /y /i %SRC_DIR%\Tools\i18n %PREFIX%\Tools\i18n
if errorlevel 1 exit 1
xcopy /s /y /i %SRC_DIR%\Tools\scripts %PREFIX%\Tools\scripts
if errorlevel 1 exit 1

del %PREFIX%\Tools\scripts\README
if errorlevel 1 exit 1
del %PREFIX%\Tools\scripts\dutree.doc
if errorlevel 1 exit 1
del %PREFIX%\Tools\scripts\idle3
if errorlevel 1 exit 1

move /y %PREFIX%\Tools\scripts\2to3 %PREFIX%\Tools\scripts\2to3.py
if errorlevel 1 exit 1
move /y %PREFIX%\Tools\scripts\pydoc3 %PREFIX%\Tools\scripts\pydoc3.py
if errorlevel 1 exit 1

:: Populate the include directory
xcopy /s /y %SRC_DIR%\Include %PREFIX%\include\
if errorlevel 1 exit 1

copy /Y %SRC_DIR%\PC\pyconfig.h %PREFIX%\include\
if errorlevel 1 exit 1

:: Populate the Scripts directory
if not exist %SCRIPTS% (mkdir %SCRIPTS%)
if errorlevel 1 exit 1

for %%x in (idle pydoc) do (
    copy /Y %SRC_DIR%\Tools\scripts\%%x3 %SCRIPTS%\%%x
    if errorlevel 1 exit 1
)

copy /Y %SRC_DIR%\Tools\scripts\2to3 %SCRIPTS%
if errorlevel 1 exit 1

:: Populate the libs directory
if not exist %PREFIX%\libs mkdir %PREFIX%\libs
if exist %SRC_DIR%\PCbuild\%BUILD_PATH%\python%VERNODOTS%%_D%.lib copy /Y %SRC_DIR%\PCbuild\%BUILD_PATH%\python%VERNODOTS%%_D%.lib %PREFIX%\libs\
if errorlevel 1 exit 1
if exist %SRC_DIR%\PCbuild\%BUILD_PATH%\python3%_D%.lib copy /Y %SRC_DIR%\PCbuild\%BUILD_PATH%\python3%_D%.lib %PREFIX%\libs\
if errorlevel 1 exit 1
if exist %SRC_DIR%\PCbuild\%BUILD_PATH%\_tkinter%_D%.lib copy /Y %SRC_DIR%\PCbuild\%BUILD_PATH%\_tkinter%_D%.lib %PREFIX%\libs\
if errorlevel 1 exit 1


:: Populate the Lib directory
del %PREFIX%\libs\libpython*.a
xcopy /s /y %SRC_DIR%\Lib %PREFIX%\Lib\
if errorlevel 1 exit 1

:: Copy venv[w]launcher scripts to venv\srcipts\nt
if exist %SRC_DIR%\PCbuild\%BUILD_PATH%\venvlauncher%_D%.exe (
  copy /Y %SRC_DIR%\PCbuild\%BUILD_PATH%\venvlauncher%_D%.exe %PREFIX%\Lib\venv\scripts\nt\python.exe
) else (
  echo "WARNING :: %SRC_DIR%\PCbuild\%BUILD_PATH%\venvlauncher%_D%.exe does not exist"
)

if exist %SRC_DIR%\PCbuild\%BUILD_PATH%\venvwlauncher%_D%.exe (
  copy /Y %SRC_DIR%\PCbuild\%BUILD_PATH%\venvwlauncher%_D%.exe %PREFIX%\Lib\venv\scripts\nt\pythonw.exe
) else (
  echo "WARNING :: %SRC_DIR%\PCbuild\%BUILD_PATH%\venvwlauncher%_D%.exe does not exist"
)


:: Remove test data to save space.
:: Though keep `support` as some things use that.
mkdir %PREFIX%\Lib\test_keep
if errorlevel 1 exit 1
move %PREFIX%\Lib\test\__init__.py %PREFIX%\Lib\test_keep\
if errorlevel 1 exit 1
move %PREFIX%\Lib\test\support %PREFIX%\Lib\test_keep\
if errorlevel 1 exit 1
rd /s /q %PREFIX%\Lib\test
if errorlevel 1 exit 1
move %PREFIX%\Lib\test_keep %PREFIX%\Lib\test
if errorlevel 1 exit 1
rd /s /q %PREFIX%\Lib\lib2to3\tests\
if errorlevel 1 exit 1

:: bytecode compile the standard library

rd /s /q %PREFIX%\Lib\lib2to3\tests\
if errorlevel 1 exit 1

:: We need our Python to be found!
if "%_D%" neq "" copy %PREFIX%\python%_D%.exe %PREFIX%\python.exe

%PREFIX%\python.exe -Wi %PREFIX%\Lib\compileall.py -f -q -x "bad_coding|badsyntax|py2_" %PREFIX%\Lib
if errorlevel 1 exit 1

:: Pickle lib2to3 Grammar
%PREFIX%\python.exe -m lib2to3 --help

:: Ensure that scripts are generated
:: https://github.com/conda-forge/python-feedstock/issues/384
%PREFIX%\python.exe %RECIPE_DIR%\fix_staged_scripts.py
if errorlevel 1 exit 1

:: Some quick tests for common failures
echo "Testing print() does not print: Hello"
%CONDA_EXE% run -p %PREFIX% cd %PREFIX% & %PREFIX%\python.exe -c "print()" 2>&1 | findstr /r /c:"Hello"
if %errorlevel% neq 1 exit /b 1

echo "Testing print('Hello') prints: Hello"
%CONDA_EXE% run -p %PREFIX% cd %PREFIX% & %PREFIX%\python.exe "print('Hello')" 2>&1 | findstr /r /c:"Hello"
if %errorlevel% neq 0 exit /b 1

echo "Testing import of os (no DLL needed) does not print: The specified module could not be found"
%CONDA_EXE% run -p %PREFIX% cd %PREFIX% & %PREFIX%\python.exe -v -c "import os" 2>&1
%CONDA_EXE% run -p %PREFIX% cd %PREFIX% & %PREFIX%\python.exe -v -c "import os" 2>&1 | findstr /r /c:"The specified module could not be found"
if %errorlevel% neq 1 exit /b 1

echo "Testing import of _sqlite3 (DLL located via PATH needed) does not print: The specified module could not be found"
%CONDA_EXE% run -p %PREFIX% cd %PREFIX% & %PREFIX%\python.exe -v -c "import _sqlite3" 2>&1
%CONDA_EXE% run -p %PREFIX% cd %PREFIX% & %PREFIX%\python.exe -v -c "import _sqlite3" 2>&1 | findstr /r /c:"The specified module could not be found"
if %errorlevel% neq 1 exit /b 1
