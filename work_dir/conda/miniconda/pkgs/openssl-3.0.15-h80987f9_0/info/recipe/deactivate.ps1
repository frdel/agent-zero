if ($Env:__CONDA_OPENSLL_CERT_FILE_SET -eq "1") {
    Remove-Item -Path Env:\SSL_CERT_FILE
    Remove-Item -Path Env:\__CONDA_OPENSLL_CERT_FILE_SET
}
