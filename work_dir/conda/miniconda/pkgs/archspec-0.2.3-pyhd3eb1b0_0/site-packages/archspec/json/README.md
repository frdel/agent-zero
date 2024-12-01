[![](https://github.com/archspec/archspec-json/workflows/JSON%20Validation/badge.svg)](https://github.com/archspec/archspec-json/actions)

# Archspec-json

The [archspec-json](https://github.com/archspec/archspec-json) repository is part of the
[Archspec](https://github.com/archspec) project. It contains data on various architectural
aspects of a platform stored in JSON format and is meant to be used as a base to develop
language specific APIs.

Currently the repository contains the following JSON files:
```console
cpu/
├── cpuid.json                     # Contains information on CPUID calls to retrieve vendor and features on x86_64
├── cpuid_schema.json              # Schema for the file above
├── microarchitectures.json        # Contains information on CPU microarchitectures
└── microarchitectures_schema.json # Schema for the file above
 ```


## License

Archspec is distributed under the terms of both the MIT license and the
Apache License (Version 2.0). Users may choose either license, at their
option.

All new contributions must be made under both the MIT and Apache-2.0
licenses.

See [LICENSE-MIT](https://github.com/archspec/archspec-json/blob/master/LICENSE-MIT),
[LICENSE-APACHE](https://github.com/archspec/archspec-json/blob/master/LICENSE-APACHE),
[COPYRIGHT](https://github.com/archspec/archspec-json/blob/master/COPYRIGHT), and
[NOTICE](https://github.com/archspec/archspec-json/blob/master/NOTICE) for details.

SPDX-License-Identifier: (Apache-2.0 OR MIT)

LLNL-CODE-811653
