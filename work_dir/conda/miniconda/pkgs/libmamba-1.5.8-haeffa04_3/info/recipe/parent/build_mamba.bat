@echo ON

:: cmd
echo "Building %PKG_NAME%."

if /I "%PKG_NAME%" == "mamba" (
	cd mamba
	%PYTHON% -m pip install . --no-deps --no-build-isolation -v
	exit 0
)

rmdir /Q /S build
mkdir build
cd build
if errorlevel 1 exit /b 1

rem most likely don't needed on Windows, just for OSX
rem set "CXXFLAGS=%CXXFLAGS% /D_LIBCPP_DISABLE_AVAILABILITY=1"

:: Generate the build files.
echo "Generating the build files..."

if /I "%PKG_NAME%" == "libmamba" (
	cmake .. ^
		%CMAKE_ARGS% ^
		-GNinja ^
		-DCMAKE_INSTALL_PREFIX=%LIBRARY_PREFIX% ^
		-DCMAKE_PREFIX_PATH=%PREFIX% ^
		-DCMAKE_BUILD_TYPE=Release ^
		-DBUILD_LIBMAMBA=ON ^
		-DBUILD_SHARED=ON  ^
		-DBUILD_MAMBA_PACKAGE=ON
)
if /I "%PKG_NAME%" == "libmambapy" (
	cmake .. ^
		%CMAKE_ARGS% ^
		-GNinja ^
		-DCMAKE_INSTALL_PREFIX=%LIBRARY_PREFIX% ^
		-DCMAKE_PREFIX_PATH=%PREFIX% ^
		-DCMAKE_BUILD_TYPE=Release ^
        -DPython_EXECUTABLE=%PYTHON% ^
		-DBUILD_LIBMAMBAPY=ON
)
if errorlevel 1 exit /b 1

:: Build.
echo "Building..."
ninja
if errorlevel 1 exit /b 1

:: Install.
echo "Installing..."
ninja install
if errorlevel 1 exit /b 1

if /I "%PKG_NAME%" == "libmambapy" (
	cd ../libmambapy
	rmdir /Q /S build
	%PYTHON% -m pip install . --no-deps --no-build-isolation -v
	del *.pyc /a /s
)

:: Error free exit.
echo "Error free exit!"
exit 0
