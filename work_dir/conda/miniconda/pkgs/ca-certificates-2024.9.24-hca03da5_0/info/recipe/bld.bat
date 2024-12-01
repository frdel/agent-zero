xcopy /y "%SRC_DIR%"\cacert.pem "%LIBRARY_PREFIX%"\ssl\
if errorlevel 1 exit 1
copy /y "%LIBRARY_PREFIX%"\ssl\cacert.pem "%LIBRARY_PREFIX%"\ssl\cert.pem
if errorlevel 1 exit 1
exit 0
