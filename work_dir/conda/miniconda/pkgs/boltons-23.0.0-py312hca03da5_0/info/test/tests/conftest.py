import sys
import re


_VERSION_MARKER = re.compile(r'_py(?P<major_version>\d)(?P<minor_version>\d)?')


def pytest_ignore_collect(path, config):
    """
    Ignore tests that end with _pyX, where X does not equal this
    interpreter's major version.
    """
    filename = path.basename
    modulename = filename.split('.', 1)[0]
    match = _VERSION_MARKER.search(modulename)
    if not match:
        return False
    major_version = match.group('major_version')
    minor_version = match.group('minor_version')

    if minor_version:
        version_match = (int(major_version), int(minor_version)) == sys.version_info[:2]
    else:
        version_match = int(major_version) == sys.version_info[0]

    return not version_match  # because this is an _ignore_ (not an include)
