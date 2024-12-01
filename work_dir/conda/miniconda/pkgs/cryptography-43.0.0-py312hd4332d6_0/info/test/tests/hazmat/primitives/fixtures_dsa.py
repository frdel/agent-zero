# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


from cryptography.hazmat.primitives.asymmetric.dsa import (
    DSAParameterNumbers,
    DSAPrivateNumbers,
    DSAPublicNumbers,
)

DSA_KEY_1024 = DSAPrivateNumbers(
    public_numbers=DSAPublicNumbers(
        parameter_numbers=DSAParameterNumbers(
            p=int(
                "d38311e2cd388c3ed698e82fdf88eb92b5a9a483dc88005d4b725ef34"
                "1eabb47cf8a7a8a41e792a156b7ce97206c4f9c5ce6fc5ae7912102b6"
                "b502e59050b5b21ce263dddb2044b652236f4d42ab4b5d6aa73189cef"
                "1ace778d7845a5c1c1c7147123188f8dc551054ee162b634d60f097f7"
                "19076640e20980a0093113a8bd73",
                16,
            ),
            q=int("96c5390a8b612c0e422bb2b0ea194a3ec935a281", 16),
            g=int(
                "06b7861abbd35cc89e79c52f68d20875389b127361ca66822138ce499"
                "1d2b862259d6b4548a6495b195aa0e0b6137ca37eb23b94074d3c3d30"
                "0042bdf15762812b6333ef7b07ceba78607610fcc9ee68491dbc1e34c"
                "d12615474e52b18bc934fb00c61d39e7da8902291c4434a4e2224c3f4"
                "fd9f93cd6f4f17fc076341a7e7d9",
                16,
            ),
        ),
        y=int(
            "6f26d98d41de7d871b6381851c9d91fa03942092ab6097e76422070edb71d"
            "b44ff568280fdb1709f8fc3feab39f1f824adaeb2a298088156ac31af1aa0"
            "4bf54f475bdcfdcf2f8a2dd973e922d83e76f016558617603129b21c70bf7"
            "d0e5dc9e68fe332e295b65876eb9a12fe6fca9f1a1ce80204646bf99b5771"
            "d249a6fea627",
            16,
        ),
    ),
    x=int("8185fee9cc7c0e91fd85503274f1cd5a3fd15a49", 16),
)

DSA_KEY_2048 = DSAPrivateNumbers(
    public_numbers=DSAPublicNumbers(
        parameter_numbers=DSAParameterNumbers(
            p=int(
                "ea1fb1af22881558ef93be8a5f8653c5a559434c49c8c2c12ace5e9c4"
                "1434c9cf0a8e9498acb0f4663c08b4484eace845f6fb17dac62c98e70"
                "6af0fc74e4da1c6c2b3fbf5a1d58ff82fc1a66f3e8b12252c40278fff"
                "9dd7f102eed2cb5b7323ebf1908c234d935414dded7f8d244e54561b0"
                "dca39b301de8c49da9fb23df33c6182e3f983208c560fb5119fbf78eb"
                "e3e6564ee235c6a15cbb9ac247baba5a423bc6582a1a9d8a2b4f0e9e3"
                "d9dbac122f750dd754325135257488b1f6ecabf21bff2947fe0d3b2cb"
                "7ffe67f4e7fcdf1214f6053e72a5bb0dd20a0e9fe6db2df0a908c36e9"
                "5e60bf49ca4368b8b892b9c79f61ef91c47567c40e1f80ac5aa66ef7",
                16,
            ),
            q=int(
                "8ec73f3761caf5fdfe6e4e82098bf10f898740dcb808204bf6b18f507"
                "192c19d",
                16,
            ),
            g=int(
                "e4c4eca88415b23ecf811c96e48cd24200fe916631a68a684e6ccb6b1"
                "913413d344d1d8d84a333839d88eee431521f6e357c16e6a93be111a9"
                "8076739cd401bab3b9d565bf4fb99e9d185b1e14d61c93700133f908b"
                "ae03e28764d107dcd2ea7674217622074bb19efff482f5f5c1a86d555"
                "1b2fc68d1c6e9d8011958ef4b9c2a3a55d0d3c882e6ad7f9f0f3c6156"
                "8f78d0706b10a26f23b4f197c322b825002284a0aca91807bba98ece9"
                "12b80e10cdf180cf99a35f210c1655fbfdd74f13b1b5046591f840387"
                "3d12239834dd6c4eceb42bf7482e1794a1601357b629ddfa971f2ed27"
                "3b146ec1ca06d0adf55dd91d65c37297bda78c6d210c0bc26e558302",
                16,
            ),
        ),
        y=int(
            "6b32e31ab9031dc4dd0b5039a78d07826687ab087ae6de4736f5b0434e125"
            "3092e8a0b231f9c87f3fc8a4cb5634eb194bf1b638b7a7889620ce6711567"
            "e36aa36cda4604cfaa601a45918371d4ccf68d8b10a50a0460eb1dc0fff62"
            "ef5e6ee4d473e18ea4a66c196fb7e677a49b48241a0b4a97128eff30fa437"
            "050501a584f8771e7280d26d5af30784039159c11ebfea10b692fd0a58215"
            "eeb18bff117e13f08db792ed4151a218e4bed8dddfb0793225bd1e9773505"
            "166f4bd8cedbb286ea28232972da7bae836ba97329ba6b0a36508e50a52a7"
            "675e476d4d4137eae13f22a9d2fefde708ba8f34bf336c6e76331761e4b06"
            "17633fe7ec3f23672fb19d27",
            16,
        ),
    ),
    x=int(
        "405772da6e90d809e77d5de796562a2dd4dfd10ef00a83a3aba6bd818a0348a1", 16
    ),
)

DSA_KEY_3072 = DSAPrivateNumbers(
    public_numbers=DSAPublicNumbers(
        parameter_numbers=DSAParameterNumbers(
            p=int(
                "f335666dd1339165af8b9a5e3835adfe15c158e4c3c7bd53132e7d582"
                "8c352f593a9a787760ce34b789879941f2f01f02319f6ae0b756f1a84"
                "2ba54c85612ed632ee2d79ef17f06b77c641b7b080aff52a03fc2462e"
                "80abc64d223723c236deeb7d201078ec01ca1fbc1763139e25099a84e"
                "c389159c409792080736bd7caa816b92edf23f2c351f90074aa5ea265"
                "1b372f8b58a0a65554db2561d706a63685000ac576b7e4562e262a142"
                "85a9c6370b290e4eb7757527d80b6c0fd5df831d36f3d1d35f12ab060"
                "548de1605fd15f7c7aafed688b146a02c945156e284f5b71282045aba"
                "9844d48b5df2e9e7a5887121eae7d7b01db7cdf6ff917cd8eb50c6bf1"
                "d54f90cce1a491a9c74fea88f7e7230b047d16b5a6027881d6f154818"
                "f06e513faf40c8814630e4e254f17a47bfe9cb519b98289935bf17673"
                "ae4c8033504a20a898d0032ee402b72d5986322f3bdfb27400561f747"
                "6cd715eaabb7338b854e51fc2fa026a5a579b6dcea1b1c0559c13d3c1"
                "136f303f4b4d25ad5b692229957",
                16,
            ),
            q=int(
                "d3eba6521240694015ef94412e08bf3cf8d635a455a398d6f210f6169"
                "041653b",
                16,
            ),
            g=int(
                "ce84b30ddf290a9f787a7c2f1ce92c1cbf4ef400e3cd7ce4978db2104"
                "d7394b493c18332c64cec906a71c3778bd93341165dee8e6cd4ca6f13"
                "afff531191194ada55ecf01ff94d6cf7c4768b82dd29cd131aaf202ae"
                "fd40e564375285c01f3220af4d70b96f1395420d778228f1461f5d0b8"
                "e47357e87b1fe3286223b553e3fc9928f16ae3067ded6721bedf1d1a0"
                "1bfd22b9ae85fce77820d88cdf50a6bde20668ad77a707d1c60fcc5d5"
                "1c9de488610d0285eb8ff721ff141f93a9fb23c1d1f7654c07c46e588"
                "36d1652828f71057b8aff0b0778ef2ca934ea9d0f37daddade2d823a4"
                "d8e362721082e279d003b575ee59fd050d105dfd71cd63154efe431a0"
                "869178d9811f4f231dc5dcf3b0ec0f2b0f9896c32ec6c7ee7d60aa971"
                "09e09224907328d4e6acd10117e45774406c4c947da8020649c3168f6"
                "90e0bd6e91ac67074d1d436b58ae374523deaf6c93c1e6920db4a080b"
                "744804bb073cecfe83fa9398cf150afa286dc7eb7949750cf5001ce10"
                "4e9187f7e16859afa8fd0d775ae",
                16,
            ),
        ),
        y=int(
            "814824e435e1e6f38daa239aad6dad21033afce6a3ebd35c1359348a0f241"
            "8871968c2babfc2baf47742148828f8612183178f126504da73566b6bab33"
            "ba1f124c15aa461555c2451d86c94ee21c3e3fc24c55527e01b1f03adcdd8"
            "ec5cb08082803a7b6a829c3e99eeb332a2cf5c035b0ce0078d3d414d31fa4"
            "7e9726be2989b8d06da2e6cd363f5a7d1515e3f4925e0b32adeae3025cc5a"
            "996f6fd27494ea408763de48f3bb39f6a06514b019899b312ec570851637b"
            "8865cff3a52bf5d54ad5a19e6e400a2d33251055d0a440b50d53f4791391d"
            "c754ad02b9eab74c46b4903f9d76f824339914db108057af7cde657d41766"
            "a99991ac8787694f4185d6f91d7627048f827b405ec67bf2fe56141c4c581"
            "d8c317333624e073e5879a82437cb0c7b435c0ce434e15965db1315d64895"
            "991e6bbe7dac040c42052408bbc53423fd31098248a58f8a67da3a39895cd"
            "0cc927515d044c1e3cb6a3259c3d0da354cce89ea3552c59609db10ee9899"
            "86527436af21d9485ddf25f90f7dff6d2bae",
            16,
        ),
    ),
    x=int(
        "b2764c46113983777d3e7e97589f1303806d14ad9f2f1ef033097de954b17706", 16
    ),
)
