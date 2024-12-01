# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Context trust constants.

You could argue that the signatures being here is not necessary; indeed, we
are not necessarily going to be able to check them *properly* (based on some
prior expectations) as the user, since this is the beginning of trust
bootstrapping, the first/backup version of the root of trust metadata.
Still, the signatures here are useful for diagnostic purposes, and, more
important, to allow self-consistency checks: that helps us avoid breaking the
chain of trust if someone accidentally lists the wrong keys down the line. (:
The discrepancy can be detected when loading the root data, and we can
decline to cache incorrect trust metadata that would make further root
updates impossible.
"""

INITIAL_TRUST_ROOT = {
    "signatures": {
        "6d4d5888398ad77465e9fd53996309187723e16509144aa6733015c960378e7a": {
            "other_headers": "04001608001d162104d2ca1d4bf5d77e7c312534284dd9c45328b685ec0502605dbb03",  # noqa: E501
            "signature": "b71c9b3aa60e77258c402e574397127bcb4bc15ef3055ada8539b0d1e355bf1415a135fb7cecc9244f839a929f6b1f82844a5b3df8d6225ec9a50b181692490f",  # noqa: E501
        },
        "508debb915ede0b16dc0cff63f250bde73c5923317b44719fcfc25cc95560c44": {
            "other_headers": "04001608001d162104e6dffee4638f24cfa60a08ba03afe1314a3a38fc050260621281",  # noqa: E501
            "signature": "29d53d4e7dbea0a3efb07266d22e57cf4df7abe004453981c631245716e1b737c7a6b4ab95f42592af70be67abf56e97020e1aa1f52b49ef39b37481f05d5701",  # noqa: E501
        },
    },
    "signed": {
        "delegations": {
            "key_mgr": {
                "pubkeys": [
                    "f24c813d23a9b26be665eee5c54680c35321061b337f862385ed6d783b0bedb0"
                ],
                "threshold": 1,
            },
            "root": {
                "pubkeys": [
                    "668a3217d72d4064edb16648435dc4a3e09a172ecee45dcab1464dcd2f402ec6",
                    "508debb915ede0b16dc0cff63f250bde73c5923317b44719fcfc25cc95560c44",
                    "6d4d5888398ad77465e9fd53996309187723e16509144aa6733015c960378e7a",
                    "e0c88b4c0721bd451b7e720dfb0d0bb6b3853f0cbcf5570edd73367d0841be51",
                ],
                "threshold": 2,
            },
        },
        "expiration": "2022-10-31T18:00:00Z",
        "metadata_spec_version": "0.6.0",
        "timestamp": "2021-03-26T00:00:00Z",
        "type": "root",
        "version": 1,
    },
}

KEY_MGR_FILE = "key_mgr.json"
