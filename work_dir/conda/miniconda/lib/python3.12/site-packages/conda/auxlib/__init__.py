"""Auxlib is an auxiliary library to the python standard library.

The aim is to provide core generic features for app development in python. Auxlib fills in some
python stdlib gaps much like `pytoolz <https://github.com/pytoolz/>`_ has for functional
programming, `pyrsistent <https://github.com/tobgu/pyrsistent/>`_ has for data structures, or
`boltons <https://github.com/mahmoud/boltons/>`_ has generally.

Major areas addressed include:
  - :ref:`packaging`: package versioning, with a clean and less invasive alternative to
    versioneer
  - :ref:`entity`: robust base class for type-enforced data models and transfer objects
  - :ref:`type_coercion`: intelligent type coercion utilities
  - :ref:`configuration`: a map implementation designed specifically to hold application
    configuration and context information
  - :ref:`factory`: factory pattern implementation
  - :ref:`path`: file path utilities especially helpful when working with various python
    package formats
  - :ref:`logz`: logging initialization routines to simplify python logging setup
  - :ref:`crypt`: simple, but correct, pycrypto wrapper

[2021-11-09] Our version of auxlib has deviated from the upstream project by a significant amount
(especially compared with the other vendored packages). Further, the upstream project has low
popularity and is no longer actively maintained. Consequently it was decided to absorb, refactor,
and replace auxlib. As a first step of this process we moved conda._vendor.auxlib to conda.auxlib.
"""

# don't mess up logging for library users
from logging import getLogger, Handler
class NullHandler(Handler):  # NOQA
    def emit(self, record):
        pass


getLogger('auxlib').addHandler(NullHandler())

__all__ = [
    "__version__", "__author__",
    "__email__", "__license__", "__copyright__",
    "__summary__", "__url__",
]

__version__ = "0.0.43"

__author__ = 'Kale Franz'
__email__ = 'kale@franz.io'
__url__ = 'https://github.com/kalefranz/auxlib'
__license__ = "ISC"
__copyright__ = "(c) 2015 Kale Franz. All rights reserved."
__summary__ = """auxiliary library to the python standard library"""


class _Null:
    """
    Examples:
        >>> len(_Null())
        0
        >>> bool(_Null())
        False
        >>> _Null().__nonzero__()
        False
    """
    def __nonzero__(self):
        return self.__bool__()

    def __bool__(self):
        return False

    def __len__(self):
        return 0

    def __eq__(self, other):
        return isinstance(other, _Null)

    def __hash__(self):
        return hash(_Null)

    def __str__(self):
        return 'Null'

    def __json__(self):
        return 'null'

    to_json = __json__


# Use this NULL object when needing to distinguish a value from None
# For example, when parsing json, you may need to determine if a json key was given and set
#   to null, or the key didn't exist at all.  There could be a bit of potential confusion here,
#   because in python null == None, while here I'm defining NULL to mean 'not defined'.
NULL = _Null()
