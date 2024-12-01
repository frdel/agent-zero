cd winbuild

if %ARCH% == 32 (
    set ARCH_STRING=x86
) else (
    set ARCH_STRING=x64
)

REM This is implicitly using WinSSL.  See Makefile.vc for more info.
nmake /f Makefile.vc MODE=dll VC=%VS_MAJOR:"=% WITH_DEVEL=%LIBRARY_PREFIX% ^
         WITH_ZLIB=dll WITH_SSH2=dll DEBUG=no ENABLE_IDN=no ENABLE_SSPI=yes ^
         MACHINE=%ARCH_STRING% ENABLE_UNICODE=yes
if errorlevel 1 exit 1

REM This is implicitly using WinSSL.  See Makefile.vc for more info.
nmake /f Makefile.vc mode=static VC=%VS_MAJOR:"=% WITH_DEVEL=%LIBRARY_PREFIX% ^
         WITH_ZLIB=dll WITH_SSH2=dll DEBUG=no ENABLE_IDN=no ENABLE_SSPI=yes ^
         MACHINE=%ARCH_STRING% ENABLE_UNICODE=yes
if errorlevel 1 exit 1

REM install static library
copy ..\builds\libcurl-vc%VS_MAJOR:"=%-%ARCH_STRING%-release-static-zlib-dll-ssh2-dll-ipv6-sspi-schannel\lib\libcurl_a.lib %LIBRARY_PREFIX%\lib\libcurl_a.lib
if %ERRORLEVEL% GTR 3 exit 1

REM install everything else
robocopy ..\builds\libcurl-vc%VS_MAJOR:"=%-%ARCH_STRING%-release-dll-zlib-dll-ssh2-dll-ipv6-sspi-schannel\ %LIBRARY_PREFIX% *.* /E
if %ERRORLEVEL% GTR 3 exit 1

exit 0
