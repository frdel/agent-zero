from collections import OrderedDict as odict  # noqa: F401
import os
from shlex import split

from ..deprecations import deprecated


def isiterable(obj):
    # and not a string
    from collections.abc import Iterable
    return not isinstance(obj, str) and isinstance(obj, Iterable)


# shlex.split() is a poor function to use for anything general purpose (like calling subprocess).
# It mishandles Unicode in Python 3 but all is not lost. We can escape it, then escape the escapes
# then call shlex.split() then un-escape that.
def shlex_split_unicode(to_split, posix=True):
    # shlex.split does its own un-escaping that we must counter.
    e_to_split = to_split.replace("\\", "\\\\")
    return split(e_to_split, posix=posix)


def Utf8NamedTemporaryFile(
    mode="w+b", buffering=-1, newline=None, suffix=None, prefix=None, dir=None, delete=True
):
    from tempfile import NamedTemporaryFile

    if "CONDA_TEST_SAVE_TEMPS" in os.environ:
        delete = False
    encoding = None
    if "b" not in mode:
        encoding = "utf-8"
    return NamedTemporaryFile(
        mode=mode,
        buffering=buffering,
        encoding=encoding,
        newline=newline,
        suffix=suffix,
        prefix=prefix,
        dir=dir,
        delete=delete,
    )
