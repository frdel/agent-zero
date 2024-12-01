#  tests for certifi-2024.8.30-py312hca03da5_0 (this is a generated file);
print('===== testing package: certifi-2024.8.30-py312hca03da5_0 =====');
print('running run_test.py');
#  --- run_test.py (begin) ---
import certifi
import pip


def certifi_tests():
    """
    Tests to validate certifi pkg
    """


if hasattr(pip, 'main'):
    pip.main(['install', "pem"])
else:
    pip._internal.main(['install', "pem"])
certificate = certifi.where()
assert certificate[-10::] == "cacert.pem", "Unable to find the certificate file"
import pem
certs = pem.parse_file(certificate)
cert_key = str(certs[0])
assert cert_key != None, "Failed to find the valid certificate "


certifi_tests()#  --- run_test.py (end) ---

print('===== certifi-2024.8.30-py312hca03da5_0 OK =====');
print("import: 'certifi'")
import certifi

