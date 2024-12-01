setlocal enableextensions
setlocal enabledelayedexpansion

pushd test_sources
if errorlevel 1 exit 1
for /f "usebackq" %%i in (`dir /b ^| findstr /i "^.*\.c$"`) do (
    clang -O2 -g %%i -o test_clang.exe
    if errorlevel 1 exit 1
    test_clang
    if errorlevel 1 exit 1
)
popd
if errorlevel 1 exit 1

pushd test_sources
if errorlevel 1 exit 1
for /f "usebackq" %%i in (`dir /b ^| findstr /i "^.*\.cpp$"`) do (
    clang++ -nostdinc++ -nostdlib -isystem "%LIBRARY_INC%\c++\v1" -I "%LIBRARY_INC%" -L "%LIBRARY_LIB%" -lc++ -lvcruntime -lucrt -lmsvcrt -O2 -g %%i -o test_clang.exe
    if errorlevel 1 exit 1
    test_clang
    if errorlevel 1 exit 1
)
popd
if errorlevel 1 exit 1

pushd test_sources\cpp11
if errorlevel 1 exit 1
for /f "usebackq" %%i in (`dir /b ^| findstr /i "^.*\.cpp$"`) do (
    clang++ -nostdinc++ -nostdlib -isystem "%LIBRARY_INC%\c++\v1" -I "%LIBRARY_INC%" -L "%LIBRARY_LIB%" -lc++ -lvcruntime -lucrt -lmsvcrt -std=c++11 -O2 -g %%i -o test_clang.exe
    if errorlevel 1 exit 1
    test_clang
    if errorlevel 1 exit 1
)
popd
if errorlevel 1 exit 1

pushd test_sources\cpp14
if errorlevel 1 exit 1
for /f "usebackq" %%i in (`dir /b ^| findstr /i "^.*\.cpp$"`) do (
    clang++ -nostdinc++ -nostdlib -isystem "%LIBRARY_INC%\c++\v1" -I "%LIBRARY_INC%" -L "%LIBRARY_LIB%" -lc++ -lvcruntime -lucrt -lmsvcrt -std=c++14 -O2 -g %%i -o test_clang.exe
    if errorlevel 1 exit 1
    test_clang
    if errorlevel 1 exit 1
)
popd
if errorlevel 1 exit 1
