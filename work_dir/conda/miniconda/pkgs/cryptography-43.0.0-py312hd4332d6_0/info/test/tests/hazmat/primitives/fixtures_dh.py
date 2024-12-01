# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


from cryptography.hazmat.primitives.asymmetric import dh

FFDH3072_P = dh.DHParameterNumbers(
    p=int(
        "ffffffffffffffffadf85458a2bb4a9aafdc5620273d3cf1d8b9c583ce2d3695a9e"
        "13641146433fbcc939dce249b3ef97d2fe363630c75d8f681b202aec4617ad3df1e"
        "d5d5fd65612433f51f5f066ed0856365553ded1af3b557135e7f57c935984f0c70e"
        "0e68b77e2a689daf3efe8721df158a136ade73530acca4f483a797abc0ab182b324"
        "fb61d108a94bb2c8e3fbb96adab760d7f4681d4f42a3de394df4ae56ede76372bb1"
        "90b07a7c8ee0a6d709e02fce1cdf7e2ecc03404cd28342f619172fe9ce98583ff8e"
        "4f1232eef28183c3fe3b1b4c6fad733bb5fcbc2ec22005c58ef1837d1683b2c6f34"
        "a26c1b2effa886b4238611fcfdcde355b3b6519035bbc34f4def99c023861b46fc9"
        "d6e6c9077ad91d2691f7f7ee598cb0fac186d91caefe130985139270b4130c93bc4"
        "37944f4fd4452e2d74dd364f2e21e71f54bff5cae82ab9c9df69ee86d2bc522363a"
        "0dabc521979b0deada1dbf9a42d5c4484e0abcd06bfa53ddef3c1b20ee3fd59d7c2"
        "5e41d2b66c62e37ffffffffffffffff",
        16,
    ),
    g=2,
)
