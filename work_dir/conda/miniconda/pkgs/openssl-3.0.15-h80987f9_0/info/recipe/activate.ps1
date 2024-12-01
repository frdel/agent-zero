if (-not $Env:SSL_CERT_FILE) {
    $Env:SSL_CERT_FILE = "$Env:CONDA_PREFIX\Library\ssl\cacert.pem"
    $Env:__CONDA_OPENSLL_CERT_FILE_SET = "1"
}
