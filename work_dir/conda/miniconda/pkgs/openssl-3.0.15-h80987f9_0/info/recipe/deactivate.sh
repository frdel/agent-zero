if [[ "${__CONDA_OPENSLL_CERT_FILE_SET:-}" == "1" ]]; then
    unset SSL_CERT_FILE
    unset __CONDA_OPENSLL_CERT_FILE_SET
fi
