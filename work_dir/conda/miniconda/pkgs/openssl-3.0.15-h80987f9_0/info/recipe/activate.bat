@echo off
if "%SSL_CERT_FILE%"=="" (
    set SSL_CERT_FILE=%CONDA_PREFIX%\Library\ssl\cacert.pem
    set __CONDA_OPENSLL_CERT_FILE_SET="1"
)
