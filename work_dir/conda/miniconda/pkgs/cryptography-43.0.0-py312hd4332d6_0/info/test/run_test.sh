

set -ex



pip check
pytest -n auto -k "not (test_x509_csr_extensions or test_no_leak_free or test_no_leak_no_malloc or test_leak or test_create_certificate_with_extensions or test_ec_derive_private_key or test_ec_private_numbers_private_key or test_create_ocsp_request or test_write_pkcs12_key_and_certificates or test_errors or test_ec_private_numbers_private_key or test_create_crl_with_idp or test_no_leak_gc or test_x25519_pubkey_from_private_key)"
exit 0
