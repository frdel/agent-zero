@echo on
setlocal EnableDelayedExpansion

if "%ARCH%"=="32" (
    set OSSL_CONFIGURE=VC-WIN32
) ELSE (
    set OSSL_CONFIGURE=VC-WIN64A
)

REM Configure step
REM
REM Conda currently does not perform prefix replacement on Windows, so
REM OPENSSLDIR cannot (reliably) be used to provide functionality such as a
REM default configuration and standard CA certificates on a per-environment
REM basis.  Given that, we set OPENSSLDIR to a location with extremely limited
REM write permissions to limit the risk of non-privileged users exploiting
REM OpenSSL's engines feature to perform arbitrary code execution attacks
REM against applications that load the OpenSSL DLLs.
REM
REM On top of that, we also set the SSL_CERT_FILE environment variable
REM via an activation script to point to the ca-certificates provided CA root file.
set PERL=%BUILD_PREFIX%\Library\bin\perl
%BUILD_PREFIX%\Library\bin\perl configure %OSSL_CONFIGURE% ^
    --prefix=%LIBRARY_PREFIX% ^
    --openssldir="%CommonProgramFiles%\ssl" ^
    enable-legacy ^
    no-fips ^
    no-module ^
    no-zlib ^
    shared

if errorlevel 1 exit 1

REM Build step
rem if "%ARCH%"=="64" (
rem     ml64 -c -Foms\uptable.obj ms\uptable.asm
rem     if errorlevel 1 exit 1
rem )

nmake
if errorlevel 1 exit 1

rem nmake -f ms\nt.mak
rem if errorlevel 1 exit 1
rem nmake -f ms\ntdll.mak
rem if errorlevel 1 exit 1

REM Testing step
nmake test
if errorlevel 1 exit 1

REM Install software components only; i.e., skip the HTML docs
nmake install_sw
if errorlevel 1 exit 1

REM Install support files for reference purposes.  (Note that the way we
REM configured OPENSSLDIR above makes these files non-functional.)
nmake install_ssldirs OPENSSLDIR=%LIBRARY_PREFIX%\ssl
if errorlevel 1 exit 1

REM Install step
rem copy out32dll\openssl.exe %PREFIX%\openssl.exe
rem copy out32\ssleay32.lib %LIBRARY_LIB%\ssleay32_static.lib
rem copy out32\libeay32.lib %LIBRARY_LIB%\libeay32_static.lib
rem copy out32dll\ssleay32.lib %LIBRARY_LIB%\ssleay32.lib
rem copy out32dll\libeay32.lib %LIBRARY_LIB%\libeay32.lib
rem copy out32dll\ssleay32.dll %LIBRARY_BIN%\ssleay32.dll
rem copy out32dll\libeay32.dll %LIBRARY_BIN%\libeay32.dll
rem mkdir %LIBRARY_INC%\openssl
rem xcopy /S inc32\openssl\*.* %LIBRARY_INC%\openssl\

REM Add pkgconfig files: adapted from https://github.com/conda-forge/openssl-feedstock/pull/106
:: install pkgconfig metadata (useful for downstream packages);
:: adapted from inspecting the conda-forge .pc files for unix, as well as
:: https://github.com/microsoft/vcpkg/blob/master/ports/openssl/install-pc-files.cmake
mkdir %LIBRARY_PREFIX%\lib\pkgconfig
for %%F in (openssl libssl libcrypto) DO (
    echo prefix=%LIBRARY_PREFIX:\=/% > %%F.pc
    type %RECIPE_DIR%\win_pkgconfig\%%F.pc.in >> %%F.pc
    echo Version: %PKG_VERSION% >> %%F.pc
    copy %%F.pc %LIBRARY_PREFIX%\lib\pkgconfig\%%F.pc
)

:: Copy the [de]activate scripts to %PREFIX%\etc\conda\[de]activate.d.
:: This will allow them to be run on environment activation.
for %%F in (activate deactivate) DO (
    if not exist %PREFIX%\etc\conda\%%F.d mkdir %PREFIX%\etc\conda\%%F.d
    copy "%RECIPE_DIR%\%%F.bat" "%PREFIX%\etc\conda\%%F.d\%PKG_NAME%_%%F.bat"
    copy "%RECIPE_DIR%\%%F.ps1" "%PREFIX%\etc\conda\%%F.d\%PKG_NAME%_%%F.ps1"
    :: Copy unix shell activation scripts, needed by Windows Bash users
    copy "%RECIPE_DIR%\%%F.sh" "%PREFIX%\etc\conda\%%F.d\%PKG_NAME%_%%F.sh"
)
