# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import pytest

from cryptography.x509 import (
    Name,
    NameAttribute,
    NameOID,
    RelativeDistinguishedName,
)


class TestRFC4514:
    def test_invalid(self, subtests):
        for value in [
            "C=US,CN=Joe , Smith,DC=example",
            ",C=US,CN=Joe , Smith,DC=example",
            "C=US,UNKNOWN=Joe , Smith,DC=example",
            "C=US,CN,DC=example",
            "C=US,FOOBAR=example",
        ]:
            with subtests.test():
                with pytest.raises(ValueError):
                    Name.from_rfc4514_string(value)

    def test_valid(self, subtests):
        for value, expected in [
            (
                r"CN=James \"Jim\" Smith\, III",
                Name(
                    [
                        NameAttribute(
                            NameOID.COMMON_NAME, 'James "Jim" Smith, III'
                        )
                    ]
                ),
            ),
            (
                r"UID=\# escape\+\,\;\00this\ ",
                Name([NameAttribute(NameOID.USER_ID, "# escape+,;\0this ")]),
            ),
            (
                r"2.5.4.3=James \"Jim\" Smith\, III",
                Name(
                    [
                        NameAttribute(
                            NameOID.COMMON_NAME, 'James "Jim" Smith, III'
                        )
                    ]
                ),
            ),
            ("ST=", Name([NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "")])),
            (
                "OU=Sales+CN=J.  Smith,DC=example,DC=net",
                Name(
                    [
                        RelativeDistinguishedName(
                            [NameAttribute(NameOID.DOMAIN_COMPONENT, "net")]
                        ),
                        RelativeDistinguishedName(
                            [
                                NameAttribute(
                                    NameOID.DOMAIN_COMPONENT, "example"
                                )
                            ]
                        ),
                        RelativeDistinguishedName(
                            [
                                NameAttribute(
                                    NameOID.ORGANIZATIONAL_UNIT_NAME, "Sales"
                                ),
                                NameAttribute(
                                    NameOID.COMMON_NAME, "J.  Smith"
                                ),
                            ]
                        ),
                    ]
                ),
            ),
            (
                "CN=cryptography.io,O=PyCA,L=,ST=,C=US",
                Name(
                    [
                        NameAttribute(NameOID.COUNTRY_NAME, "US"),
                        NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, ""),
                        NameAttribute(NameOID.LOCALITY_NAME, ""),
                        NameAttribute(NameOID.ORGANIZATION_NAME, "PyCA"),
                        NameAttribute(NameOID.COMMON_NAME, "cryptography.io"),
                    ]
                ),
            ),
            (
                r"C=US,CN=Joe \, Smith,DC=example",
                Name(
                    [
                        NameAttribute(NameOID.DOMAIN_COMPONENT, "example"),
                        NameAttribute(NameOID.COMMON_NAME, "Joe , Smith"),
                        NameAttribute(NameOID.COUNTRY_NAME, "US"),
                    ]
                ),
            ),
            (
                r"C=US,CN=Jane \"J\,S\" Smith,DC=example",
                Name(
                    [
                        NameAttribute(NameOID.DOMAIN_COMPONENT, "example"),
                        NameAttribute(NameOID.COMMON_NAME, 'Jane "J,S" Smith'),
                        NameAttribute(NameOID.COUNTRY_NAME, "US"),
                    ]
                ),
            ),
            (
                'C=US,CN=\\"Jane J\\,S Smith\\",DC=example',
                Name(
                    [
                        NameAttribute(NameOID.DOMAIN_COMPONENT, "example"),
                        NameAttribute(NameOID.COMMON_NAME, '"Jane J,S Smith"'),
                        NameAttribute(NameOID.COUNTRY_NAME, "US"),
                    ]
                ),
            ),
            (
                'C=US,CN=\\"Jane \\"J\\,S\\" Smith\\",DC=example',
                Name(
                    [
                        NameAttribute(NameOID.DOMAIN_COMPONENT, "example"),
                        NameAttribute(
                            NameOID.COMMON_NAME, '"Jane "J,S" Smith"'
                        ),
                        NameAttribute(NameOID.COUNTRY_NAME, "US"),
                    ]
                ),
            ),
            (
                r"C=US,CN=Jane=Smith,DC=example",
                Name(
                    [
                        NameAttribute(NameOID.DOMAIN_COMPONENT, "example"),
                        NameAttribute(NameOID.COMMON_NAME, "Jane=Smith"),
                        NameAttribute(NameOID.COUNTRY_NAME, "US"),
                    ]
                ),
            ),
            (r"CN=#616263", Name([NameAttribute(NameOID.COMMON_NAME, "abc")])),
            (r"CN=👍", Name([NameAttribute(NameOID.COMMON_NAME, "👍")])),
            (
                "CN=\\\\123",
                Name([NameAttribute(NameOID.COMMON_NAME, "\\123")]),
            ),
            ("CN=\\\\\\;", Name([NameAttribute(NameOID.COMMON_NAME, "\\;")])),
            (
                "CN=\\\\#123",
                Name([NameAttribute(NameOID.COMMON_NAME, "\\#123")]),
            ),
            (
                "2.5.4.10=abc",
                Name([NameAttribute(NameOID.ORGANIZATION_NAME, "abc")]),
            ),
            ("", Name([])),
        ]:
            with subtests.test():
                result = Name.from_rfc4514_string(value)
                assert result == expected

    def test_attr_name_override(self):
        assert Name.from_rfc4514_string(
            "CN=Santa Claus,E=santa@north.pole", {"E": NameOID.EMAIL_ADDRESS}
        ) == Name(
            [
                NameAttribute(NameOID.EMAIL_ADDRESS, "santa@north.pole"),
                NameAttribute(NameOID.COMMON_NAME, "Santa Claus"),
            ]
        )

        assert Name.from_rfc4514_string(
            "CN=Santa Claus", {"CN": NameOID.EMAIL_ADDRESS}
        ) == Name(
            [
                NameAttribute(NameOID.EMAIL_ADDRESS, "Santa Claus"),
            ]
        )

    def test_generate_parse(self):
        name_value = Name(
            [
                NameAttribute(NameOID.COMMON_NAME, "Common Name 1"),
                NameAttribute(NameOID.LOCALITY_NAME, "City for Name 1"),
                NameAttribute(
                    NameOID.ORGANIZATION_NAME, "Name 1 Organization"
                ),
            ]
        )

        assert (
            Name.from_rfc4514_string(name_value.rfc4514_string()) == name_value
        )

        name_string = "O=Organization,L=City,CN=Common Name"
        assert (
            Name.from_rfc4514_string(name_string).rfc4514_string()
            == name_string
        )
