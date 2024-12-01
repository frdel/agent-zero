# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Common Python package format utilities."""

import platform
import re
import sys
import warnings
from collections import namedtuple
from configparser import ConfigParser
from csv import reader as csv_reader
from email.parser import HeaderParser
from errno import ENOENT
from io import StringIO
from itertools import chain
from logging import getLogger
from os import name as os_name
from os import scandir, strerror
from os.path import basename, dirname, isdir, isfile, join, lexists
from posixpath import normpath as posix_normpath

from ... import CondaError
from ...auxlib.decorators import memoizedproperty
from ..compat import open_utf8
from ..iterators import groupby_to_dict as groupby
from ..path import (
    get_major_minor_version,
    get_python_site_packages_short_path,
    pyc_path,
    win_path_ok,
)

try:
    from frozendict import frozendict
except ImportError:
    from ..._vendor.frozendict import frozendict

log = getLogger(__name__)

# TODO: complete this list
PYPI_TO_CONDA = {
    "graphviz": "python-graphviz",
}
# TODO: complete this list
PYPI_CONDA_DEPS = {
    "graphviz": ["graphviz"],  # What version constraints?
}
# This regex can process requirement including or not including name.
# This is useful for parsing, for example, `Python-Version`
PARTIAL_PYPI_SPEC_PATTERN = re.compile(
    r"""
    # Text needs to be stripped and all extra spaces replaced by single spaces
    (?P<name>^[A-Z0-9][A-Z0-9._-]*)?
    \s?
    (\[(?P<extras>.*)\])?
    \s?
    (?P<constraints>\(? \s? ([\w\d<>=!~,\s\.\*+-]*) \s? \)? )?
    \s?
""",
    re.VERBOSE | re.IGNORECASE,
)
PY_FILE_RE = re.compile(r"^[^\t\n\r\f\v]+/site-packages/[^\t\n\r\f\v]+\.py$")
PySpec = namedtuple("PySpec", ["name", "extras", "constraints", "marker", "url"])


class MetadataWarning(Warning):
    pass


# Dist classes
# -----------------------------------------------------------------------------
class PythonDistribution:
    """Base object describing a python distribution based on path to anchor file."""

    MANIFEST_FILES = ()  # Only one is used, but many names available
    REQUIRES_FILES = ()  # Only one is used, but many names available
    MANDATORY_FILES = ()
    ENTRY_POINTS_FILES = ("entry_points.txt",)

    @staticmethod
    def init(prefix_path, anchor_file, python_version):
        if anchor_file.endswith(".egg-link"):
            return PythonEggLinkDistribution(prefix_path, anchor_file, python_version)
        elif ".dist-info" in anchor_file:
            return PythonInstalledDistribution(prefix_path, anchor_file, python_version)
        elif anchor_file.endswith(".egg-info"):
            anchor_full_path = join(prefix_path, win_path_ok(anchor_file))
            sp_reference = basename(anchor_file)
            return PythonEggInfoDistribution(
                anchor_full_path, python_version, sp_reference
            )
        elif ".egg-info" in anchor_file:
            anchor_full_path = join(prefix_path, win_path_ok(dirname(anchor_file)))
            sp_reference = basename(dirname(anchor_file))
            return PythonEggInfoDistribution(
                anchor_full_path, python_version, sp_reference
            )
        elif ".egg" in anchor_file:
            anchor_full_path = join(prefix_path, win_path_ok(dirname(anchor_file)))
            sp_reference = basename(dirname(anchor_file))
            return PythonEggInfoDistribution(
                anchor_full_path, python_version, sp_reference
            )
        else:
            raise NotImplementedError()

    def __init__(self, anchor_full_path, python_version):
        # Don't call PythonDistribution directly. Use the init() static method.
        self.anchor_full_path = anchor_full_path
        self.python_version = python_version

        if anchor_full_path and isfile(anchor_full_path):
            self._metadata_dir_full_path = dirname(anchor_full_path)
        elif anchor_full_path and isdir(anchor_full_path):
            self._metadata_dir_full_path = anchor_full_path
        else:
            raise RuntimeError(f"Path not found: {anchor_full_path}")

        self._check_files()
        self._metadata = PythonDistributionMetadata(anchor_full_path)
        self._provides_file_data = ()
        self._requires_file_data = ()

    def _check_files(self):
        """Check the existence of mandatory files for a given distribution."""
        for fname in self.MANDATORY_FILES:
            if self._metadata_dir_full_path:
                fpath = join(self._metadata_dir_full_path, fname)
                if not isfile(fpath):
                    raise OSError(ENOENT, strerror(ENOENT), fpath)

    def _check_path_data(self, path, checksum, size):
        """Normalizes record data content and format."""
        if checksum:
            assert checksum.startswith("sha256="), (
                self._metadata_dir_full_path,
                path,
                checksum,
            )
            checksum = checksum[7:]
        else:
            checksum = None
        size = int(size) if size else None

        return path, checksum, size

    @staticmethod
    def _parse_requires_file_data(data, global_section="__global__"):
        # https://setuptools.readthedocs.io/en/latest/formats.html#requires-txt
        requires = {}
        lines = [line.strip() for line in data.split("\n") if line]

        if lines and not (lines[0].startswith("[") and lines[0].endswith("]")):
            # Add dummy section for unsectioned items
            lines = [f"[{global_section}]"] + lines

        # Parse sections
        for line in lines:
            if line.startswith("[") and line.endswith("]"):
                section = line.strip()[1:-1]
                requires[section] = []
                continue

            if line.strip():
                requires[section].append(line.strip())

        # Adapt to *standard* requirements (add env markers to requirements)
        reqs = []
        extras = []
        for section, values in requires.items():
            if section == global_section:
                # This is the global section (same as dist_requires)
                reqs.extend(values)
            elif section.startswith(":"):
                # The section is used as a marker
                # Example: ":python_version < '3'"
                marker = section.replace(":", "; ")
                new_values = [v + marker for v in values]
                reqs.extend(new_values)
            else:
                # The section is an extra, i.e. "docs", or "tests"...
                extras.append(section)
                marker = f'; extra == "{section}"'
                new_values = [v + marker for v in values]
                reqs.extend(new_values)

        return frozenset(reqs), extras

    @staticmethod
    def _parse_entries_file_data(data):
        # https://setuptools.readthedocs.io/en/latest/formats.html#entry-points-txt-entry-point-plugin-metadata
        # FIXME: Use pkg_resources which provides API for this?
        entries_data = {}
        config = ConfigParser()
        config.optionxform = lambda x: x  # Avoid lowercasing keys
        try:
            do_read = config.read_file
        except AttributeError:
            do_read = config.readfp
        do_read(StringIO(data))
        for section in config.sections():
            entries_data[section] = dict(config.items(section))

        return entries_data

    def _load_requires_provides_file(self):
        # https://setuptools.readthedocs.io/en/latest/formats.html#requires-txt
        # FIXME: Use pkg_resources which provides API for this?
        requires, extras = None, None
        for fname in self.REQUIRES_FILES:
            fpath = join(self._metadata_dir_full_path, fname)
            if isfile(fpath):
                with open_utf8(fpath) as fh:
                    data = fh.read()

                requires, extras = self._parse_requires_file_data(data)
                self._provides_file_data = extras
                self._requires_file_data = requires
                break

        return requires, extras

    @memoizedproperty
    def manifest_full_path(self):
        manifest_full_path = None
        if self._metadata_dir_full_path:
            for fname in self.MANIFEST_FILES:
                manifest_full_path = join(self._metadata_dir_full_path, fname)
                if isfile(manifest_full_path):
                    break
        return manifest_full_path

    def get_paths(self):
        """
        Read the list of installed paths from record or source file.

        Example
        -------
        [(u'skdata/__init__.py', u'sha256=47DEQpj8HBSa-_TImW-5JCeuQeRkm5NMpJWZG3hSuFU', 0),
         (u'skdata/diabetes.py', None, None),
         ...
        ]
        """
        manifest_full_path = self.manifest_full_path
        if manifest_full_path:
            python_version = self.python_version
            sp_dir = get_python_site_packages_short_path(python_version) + "/"
            prepend_metadata_dirname = (
                basename(manifest_full_path) == "installed-files.txt"
            )
            if prepend_metadata_dirname:
                path_prepender = basename(dirname(manifest_full_path)) + "/"
            else:
                path_prepender = ""

            def process_csv_row(reader):
                seen = []
                records = []
                for row in reader:
                    cleaned_path = posix_normpath(f"{sp_dir}{path_prepender}{row[0]}")
                    if len(row) == 3:
                        checksum, size = row[1:]
                        if checksum:
                            assert checksum.startswith("sha256="), (
                                self._metadata_dir_full_path,
                                cleaned_path,
                                checksum,
                            )
                            checksum = checksum[7:]
                        else:
                            checksum = None
                        size = int(size) if size else None
                    else:
                        checksum = size = None
                    if cleaned_path not in seen and row[0]:
                        seen.append(cleaned_path)
                        records.append((cleaned_path, checksum, size))
                return tuple(records)

            csv_delimiter = ","
            with open_utf8(manifest_full_path) as csvfile:
                record_reader = csv_reader(csvfile, delimiter=csv_delimiter)
                # format of each record is (path, checksum, size)
                records = process_csv_row(record_reader)
            files_set = {record[0] for record in records}

            _pyc_path, _py_file_re = pyc_path, PY_FILE_RE
            py_ver_mm = get_major_minor_version(python_version, with_dot=False)
            missing_pyc_files = (
                ff
                for ff in (
                    _pyc_path(f, py_ver_mm) for f in files_set if _py_file_re.match(f)
                )
                if ff not in files_set
            )
            records = sorted(
                (*records, *((pf, None, None) for pf in missing_pyc_files))
            )
            return records

        return []

    def get_dist_requirements(self):
        # FIXME: On some packages, requirements are not added to metadata,
        # but on a separate requires.txt, see: python setup.py develop for
        # anaconda-client. This is setuptools behavior.
        # TODO: what is the dependency_links.txt on the same example?
        data = self._metadata.get_dist_requirements()
        if self._requires_file_data:
            data = self._requires_file_data
        elif not data:
            self._load_requires_provides_file()
            data = self._requires_file_data
        return data

    def get_python_requirements(self):
        return self._metadata.get_python_requirements()

    def get_external_requirements(self):
        return self._metadata.get_external_requirements()

    def get_extra_provides(self):
        # FIXME: On some packages, requirements are not added to metadata,
        # but on a separate requires.txt, see: python setup.py develop for
        # anaconda-client. This is setuptools behavior.
        data = self._metadata.get_extra_provides()
        if self._provides_file_data:
            data = self._provides_file_data
        elif not data:
            self._load_requires_provides_file()
            data = self._provides_file_data

        return data

    def get_conda_dependencies(self):
        """
        Process metadata fields providing dependency information.

        This includes normalizing fields, and evaluating environment markers.
        """
        python_spec = "python {}.*".format(".".join(self.python_version.split(".")[:2]))

        def pyspec_to_norm_req(pyspec):
            conda_name = pypi_name_to_conda_name(norm_package_name(pyspec.name))
            return (
                f"{conda_name} {pyspec.constraints}"
                if pyspec.constraints
                else conda_name
            )

        reqs = self.get_dist_requirements()
        pyspecs = tuple(parse_specification(req) for req in reqs)
        marker_groups = groupby(lambda ps: ps.marker.split("==", 1)[0].strip(), pyspecs)
        depends = {pyspec_to_norm_req(pyspec) for pyspec in marker_groups.pop("", ())}
        extras = marker_groups.pop("extra", ())
        execution_context = {
            "python_version": self.python_version,
        }
        depends.update(
            pyspec_to_norm_req(pyspec)
            for pyspec in chain.from_iterable(marker_groups.values())
            if interpret(pyspec.marker, execution_context)
        )
        constrains = {
            pyspec_to_norm_req(pyspec) for pyspec in extras if pyspec.constraints
        }
        depends.add(python_spec)

        return sorted(depends), sorted(constrains)

    def get_optional_dependencies(self):
        raise NotImplementedError

    def get_entry_points(self):
        # TODO: need to add entry points, "exports," and other files that might
        # not be in RECORD
        for fname in self.ENTRY_POINTS_FILES:
            fpath = join(self._metadata_dir_full_path, fname)
            if isfile(fpath):
                with open_utf8(fpath) as fh:
                    data = fh.read()
        return self._parse_entries_file_data(data)

    @property
    def name(self):
        return self._metadata.name

    @property
    def norm_name(self):
        return norm_package_name(self.name)

    @property
    def conda_name(self):
        return pypi_name_to_conda_name(self.norm_name)

    @property
    def version(self):
        return self._metadata.version


class PythonInstalledDistribution(PythonDistribution):
    """
    Python distribution installed via distutils.

    Notes
    -----
      - https://www.python.org/dev/peps/pep-0376/
    """

    MANIFEST_FILES = ("RECORD",)
    REQUIRES_FILES = ()
    MANDATORY_FILES = ("METADATA",)
    # FIXME: Do this check? Disabled for tests where only Metadata file is stored
    # MANDATORY_FILES = ('METADATA', 'RECORD', 'INSTALLER')
    ENTRY_POINTS_FILES = ()

    is_manageable = True

    def __init__(self, prefix_path, anchor_file, python_version):
        anchor_full_path = join(prefix_path, win_path_ok(dirname(anchor_file)))
        super().__init__(anchor_full_path, python_version)
        self.sp_reference = basename(dirname(anchor_file))


class PythonEggInfoDistribution(PythonDistribution):
    """
    Python distribution installed via setuptools.

    Notes
    -----
      - http://peak.telecommunity.com/DevCenter/EggFormats
    """

    MANIFEST_FILES = ("installed-files.txt", "SOURCES", "SOURCES.txt")
    REQUIRES_FILES = ("requires.txt", "depends.txt")
    MANDATORY_FILES = ()
    ENTRY_POINTS_FILES = ("entry_points.txt",)

    def __init__(self, anchor_full_path, python_version, sp_reference):
        super().__init__(anchor_full_path, python_version)
        self.sp_reference = sp_reference

    @property
    def is_manageable(self):
        return (
            self.manifest_full_path
            and basename(self.manifest_full_path) == "installed-files.txt"
        )


class PythonEggLinkDistribution(PythonEggInfoDistribution):
    is_manageable = False

    def __init__(self, prefix_path, anchor_file, python_version):
        anchor_full_path = get_dist_file_from_egg_link(anchor_file, prefix_path)
        sp_reference = None  # This can be None in case the egg-info is no longer there
        super().__init__(anchor_full_path, python_version, sp_reference)


# Python distribution/eggs metadata
# -----------------------------------------------------------------------------


class PythonDistributionMetadata:
    """
    Object representing the metada of a Python Distribution given by anchor
    file (or directory) path.

    This metadata is extracted from a single file. Python distributions might
    create additional files that complement this metadata information, but
    that is handled at the python distribution level.

    Notes
    -----
      - https://packaging.python.org/specifications/core-metadata/
      - Metadata 2.1: https://www.python.org/dev/peps/pep-0566/
      - Metadata 2.0: https://www.python.org/dev/peps/pep-0426/ (Withdrawn)
      - Metadata 1.2: https://www.python.org/dev/peps/pep-0345/
      - Metadata 1.1: https://www.python.org/dev/peps/pep-0314/
      - Metadata 1.0: https://www.python.org/dev/peps/pep-0241/
    """

    FILE_NAMES = ("METADATA", "PKG-INFO")

    # Python Packages Metadata 2.1
    # -----------------------------------------------------------------------------
    SINGLE_USE_KEYS = frozendict(
        (
            ("Metadata-Version", "metadata_version"),
            ("Name", "name"),
            ("Version", "version"),
            # ('Summary', 'summary'),
            # ('Description', 'description'),
            # ('Description-Content-Type', 'description_content_type'),
            # ('Keywords', 'keywords'),
            # ('Home-page', 'home_page'),
            # ('Download-URL', 'download_url'),
            # ('Author', 'author'),
            # ('Author-email', 'author_email'),
            # ('Maintainer', 'maintainer'),
            # ('Maintainer-email', 'maintainer_email'),
            ("License", "license"),
            # # Deprecated
            # ('Obsoleted-By', 'obsoleted_by'),  # Note: See 2.0
            # ('Private-Version', 'private_version'),  # Note: See 2.0
        )
    )
    MULTIPLE_USE_KEYS = frozendict(
        (
            ("Platform", "platform"),
            ("Supported-Platform", "supported_platform"),
            # ('Classifier', 'classifier'),
            ("Requires-Dist", "requires_dist"),
            ("Requires-External", "requires_external"),
            ("Requires-Python", "requires_python"),
            # ('Project-URL', 'project_url'),
            ("Provides-Extra", "provides_extra"),
            # ('Provides-Dist', 'provides_dist'),
            # ('Obsoletes-Dist', 'obsoletes_dist'),
            # # Deprecated
            # ('Extension', 'extension'),  # Note: See 2.0
            # ('Obsoletes', 'obsoletes'),
            # ('Provides', 'provides'),
            ("Requires", "requires"),
            # ('Setup-Requires-Dist', 'setup_requires_dist'),  # Note: See 2.0
        )
    )

    def __init__(self, path):
        metadata_path = self._process_path(path, self.FILE_NAMES)
        self._path = path
        self._data = self._read_metadata(metadata_path)

    @staticmethod
    def _process_path(path, metadata_filenames):
        """Find metadata file inside dist-info folder, or check direct file."""
        metadata_path = None
        if path:
            if isdir(path):
                for fname in metadata_filenames:
                    fpath = join(path, fname)
                    if isfile(fpath):
                        metadata_path = fpath
                        break
            elif isfile(path):
                # '<pkg>.egg-info' file contains metadata directly
                filenames = [".egg-info"]
                if metadata_filenames:
                    filenames.extend(metadata_filenames)
                assert any(path.endswith(filename) for filename in filenames)
                metadata_path = path
            else:
                # `path` does not exist
                warnings.warn("Metadata path not found", MetadataWarning)
        else:
            warnings.warn("Metadata path not found", MetadataWarning)

        return metadata_path

    @classmethod
    def _message_to_dict(cls, message):
        """
        Convert the RFC-822 headers data into a dictionary.

        `message` is an email.parser.Message instance.

        The canonical method to transform metadata fields into such a data
        structure is as follows:
          - The original key-value format should be read with
            email.parser.HeaderParser
          - All transformed keys should be reduced to lower case. Hyphens
            should be replaced with underscores, but otherwise should retain
            all other characters
          - The transformed value for any field marked with "(Multiple-use")
            should be a single list containing all the original values for the
            given key
          - The Keywords field should be converted to a list by splitting the
            original value on whitespace characters
          - The message body, if present, should be set to the value of the
            description key.
          - The result should be stored as a string-keyed dictionary.
        """
        new_data = {}

        if message:
            for key, value in message.items():
                if key in cls.MULTIPLE_USE_KEYS:
                    new_key = cls.MULTIPLE_USE_KEYS[key]
                    if new_key not in new_data:
                        new_data[new_key] = [value]
                    else:
                        new_data[new_key].append(value)

                elif key in cls.SINGLE_USE_KEYS:
                    new_key = cls.SINGLE_USE_KEYS[key]
                    new_data[new_key] = value

            # TODO: Handle license later on for convenience

        return new_data

    @classmethod
    def _read_metadata(cls, fpath):
        """Read the original format which is stored as RFC-822 headers."""
        data = {}
        if fpath and isfile(fpath):
            parser = HeaderParser()

            # FIXME: Is this a correct assumption for the encoding?
            # This was needed due to some errors on windows
            with open_utf8(fpath) as fp:
                data = parser.parse(fp)

        return cls._message_to_dict(data)

    def _get_multiple_data(self, keys):
        """
        Helper method to get multiple data values by keys.

        Keys is an iterable including the preferred key in order, to include
        values of key that might have been replaced (deprecated), for example
        keys can be ['requires_dist', 'requires'], where the key 'requires' is
        deprecated and replaced by 'requires_dist'.
        """
        data = []
        if self._data:
            for key in keys:
                raw_data = self._data.get(key, [])
                for req in raw_data:
                    data.append(req.strip())

                if data:
                    break

        return frozenset(data)

    def get_dist_requirements(self):
        """
        Changed in version 2.1: The field format specification was relaxed to
        accept the syntax used by popular publishing tools.

        Each entry contains a string naming some other distutils project
        required by this distribution.

        The format of a requirement string contains from one to four parts:
          - A project name, in the same format as the Name: field. The only
            mandatory part.
          - A comma-separated list of ‘extra’ names. These are defined by the
            required project, referring to specific features which may need
            extra dependencies.
          - A version specifier. Tools parsing the format should accept
            optional parentheses around this, but tools generating it should
            not use parentheses.
          - An environment marker after a semicolon. This means that the
            requirement is only needed in the specified conditions.

        This field may be followed by an environment marker after a semicolon.

        Example
        -------
        frozenset(['pkginfo', 'PasteDeploy', 'zope.interface (>3.5.0)',
                   'pywin32 >1.0; sys_platform == "win32"'])

        Return 'Requires' if 'Requires-Dist' is empty.
        """
        return self._get_multiple_data(["requires_dist", "requires"])

    def get_python_requirements(self):
        """
        New in version 1.2.

        This field specifies the Python version(s) that the distribution is
        guaranteed to be compatible with. Installation tools may look at this
        when picking which version of a project to install.

        The value must be in the format specified in Version specifiers.

        This field may be followed by an environment marker after a semicolon.

        Example
        -------
        frozenset(['>=3', '>2.6,!=3.0.*,!=3.1.*', '~=2.6',
                   '>=3; sys_platform == "win32"'])
        """
        return self._get_multiple_data(["requires_python"])

    def get_external_requirements(self):
        """
        Changed in version 2.1: The field format specification was relaxed to
        accept the syntax used by popular publishing tools.

        Each entry contains a string describing some dependency in the system
        that the distribution is to be used. This field is intended to serve
        as a hint to downstream project maintainers, and has no semantics
        which are meaningful to the distutils distribution.

        The format of a requirement string is a name of an external dependency,
        optionally followed by a version declaration within parentheses.

        This field may be followed by an environment marker after a semicolon.

        Because they refer to non-Python software releases, version numbers for
        this field are not required to conform to the format specified in PEP
        440: they should correspond to the version scheme used by the external
        dependency.

        Notice that there’s is no particular rule on the strings to be used!

        Example
        -------
        frozenset(['C', 'libpng (>=1.5)', 'make; sys_platform != "win32"'])
        """
        return self._get_multiple_data(["requires_external"])

    def get_extra_provides(self):
        """
        New in version 2.1.

        A string containing the name of an optional feature. Must be a valid
        Python identifier. May be used to make a dependency conditional on
        hether the optional feature has been requested.

        Example
        -------
        frozenset(['pdf', 'doc', 'test'])
        """
        return self._get_multiple_data(["provides_extra"])

    def get_dist_provides(self):
        """
        New in version 1.2.

        Changed in version 2.1: The field format specification was relaxed to
        accept the syntax used by popular publishing tools.

        Each entry contains a string naming a Distutils project which is
        contained within this distribution. This field must include the project
        identified in the Name field, followed by the version : Name (Version).

        A distribution may provide additional names, e.g. to indicate that
        multiple projects have been bundled together. For instance, source
        distributions of the ZODB project have historically included the
        transaction project, which is now available as a separate distribution.
        Installing such a source distribution satisfies requirements for both
        ZODB and transaction.

        A distribution may also provide a “virtual” project name, which does
        not correspond to any separately-distributed project: such a name might
        be used to indicate an abstract capability which could be supplied by
        one of multiple projects. E.g., multiple projects might supply RDBMS
        bindings for use by a given ORM: each project might declare that it
        provides ORM-bindings, allowing other projects to depend only on having
        at most one of them installed.

        A version declaration may be supplied and must follow the rules
        described in Version specifiers. The distribution’s version number
        will be implied if none is specified.

        This field may be followed by an environment marker after a semicolon.

        Return `Provides` in case `Provides-Dist` is empty.
        """
        return self._get_multiple_data(["provides_dist", "provides"])

    def get_dist_obsolete(self):
        """
        New in version 1.2.

        Changed in version 2.1: The field format specification was relaxed to
        accept the syntax used by popular publishing tools.

        Each entry contains a string describing a distutils project’s
        distribution which this distribution renders obsolete, meaning that
        the two projects should not be installed at the same time.

        Version declarations can be supplied. Version numbers must be in the
        format specified in Version specifiers [1].

        The most common use of this field will be in case a project name
        changes, e.g. Gorgon 2.3 gets subsumed into Torqued Python 1.0. When
        you install Torqued Python, the Gorgon distribution should be removed.

        This field may be followed by an environment marker after a semicolon.

        Return `Obsoletes` in case `Obsoletes-Dist` is empty.

        Example
        -------
        frozenset(['Gorgon', "OtherProject (<3.0) ; python_version == '2.7'"])

        Notes
        -----
        - [1] https://packaging.python.org/specifications/version-specifiers/
        """
        return self._get_multiple_data(["obsoletes_dist", "obsoletes"])

    def get_classifiers(self):
        """
        Classifiers are described in PEP 301, and the Python Package Index
        publishes a dynamic list of currently defined classifiers.

        This field may be followed by an environment marker after a semicolon.

        Example
        -------
        frozenset(['Development Status :: 4 - Beta',
                   "Environment :: Console (Text Based) ; os_name == "posix"])
        """
        return self._get_multiple_data(["classifier"])

    @property
    def name(self):
        return self._data.get("name")  # TODO: Check for existence?

    @property
    def version(self):
        return self._data.get("version")  # TODO: Check for existence?


# Helper functions
# -----------------------------------------------------------------------------
def norm_package_name(name):
    return name.replace(".", "-").replace("_", "-").lower() if name else ""


def pypi_name_to_conda_name(pypi_name):
    return PYPI_TO_CONDA.get(pypi_name, pypi_name) if pypi_name else ""


def norm_package_version(version):
    """Normalize a version by removing extra spaces and parentheses."""
    if version:
        version = ",".join(v.strip() for v in version.split(",")).strip()

        if version.startswith("(") and version.endswith(")"):
            version = version[1:-1]

        version = "".join(v for v in version if v.strip())
    else:
        version = ""

    return version


def split_spec(spec, sep):
    """Split a spec by separator and return stripped start and end parts."""
    parts = spec.rsplit(sep, 1)
    spec_start = parts[0].strip()
    spec_end = ""
    if len(parts) == 2:
        spec_end = parts[-1].strip()
    return spec_start, spec_end


def parse_specification(spec):
    """
    Parse a requirement from a python distribution metadata and return a
    namedtuple with name, extras, constraints, marker and url components.

    This method does not enforce strict specifications but extracts the
    information which is assumed to be *correct*. As such no errors are raised.

    Example
    -------
    PySpec(name='requests', extras=['security'], constraints='>=3.3.0',
           marker='foo >= 2.7 or bar == 1', url=''])
    """
    name, extras, const = spec, [], ""

    # Remove excess whitespace
    spec = " ".join(p for p in spec.split(" ") if p).strip()

    # Extract marker (Assumes that there can only be one ';' inside the spec)
    spec, marker = split_spec(spec, ";")

    # Extract url (Assumes that there can only be one '@' inside the spec)
    spec, url = split_spec(spec, "@")

    # Find name, extras and constraints
    r = PARTIAL_PYPI_SPEC_PATTERN.match(spec)
    if r:
        # Normalize name
        name = r.group("name")
        name = norm_package_name(name)  # TODO: Do we want this or not?

        # Clean extras
        extras = r.group("extras")
        extras = [e.strip() for e in extras.split(",") if e] if extras else []

        # Clean constraints
        const = r.group("constraints")
        const = "".join(c for c in const.split(" ") if c).strip()
        if const.startswith("(") and const.endswith(")"):
            # Remove parens
            const = const[1:-1]
        const = const.replace("-", ".")

    return PySpec(name=name, extras=extras, constraints=const, marker=marker, url=url)


def get_site_packages_anchor_files(site_packages_path, site_packages_dir):
    """Get all the anchor files for the site packages directory."""
    site_packages_anchor_files = set()
    for entry in scandir(site_packages_path):
        fname = entry.name
        anchor_file = None
        if fname.endswith(".dist-info"):
            anchor_file = "{}/{}/{}".format(site_packages_dir, fname, "RECORD")
        elif fname.endswith(".egg-info"):
            if isfile(join(site_packages_path, fname)):
                anchor_file = f"{site_packages_dir}/{fname}"
            else:
                anchor_file = "{}/{}/{}".format(site_packages_dir, fname, "PKG-INFO")
        elif fname.endswith(".egg"):
            if isdir(join(site_packages_path, fname)):
                anchor_file = "{}/{}/{}/{}".format(
                    site_packages_dir, fname, "EGG-INFO", "PKG-INFO"
                )
            # FIXME: If it is a .egg file, we need to unzip the content to be
            # able. Do this once and leave the directory, and remove the egg
            # (which is a zip file in disguise?)
        elif fname.endswith(".egg-link"):
            anchor_file = f"{site_packages_dir}/{fname}"
        elif fname.endswith(".pth"):
            continue
        else:
            continue

        if anchor_file:
            site_packages_anchor_files.add(anchor_file)

    return site_packages_anchor_files


def get_dist_file_from_egg_link(egg_link_file, prefix_path):
    """Return the egg info file path following an egg link."""
    egg_info_full_path = None

    egg_link_path = join(prefix_path, win_path_ok(egg_link_file))
    try:
        with open_utf8(egg_link_path) as fh:
            # See: https://setuptools.readthedocs.io/en/latest/formats.html#egg-links
            # "...Each egg-link file should contain a single file or directory name
            # with no newlines..."
            egg_link_contents = fh.readlines()[0].strip()
    except UnicodeDecodeError:
        from locale import getpreferredencoding

        with open_utf8(egg_link_path, encoding=getpreferredencoding()) as fh:
            egg_link_contents = fh.readlines()[0].strip()

    if lexists(egg_link_contents):
        egg_info_fnames = tuple(
            name
            for name in (entry.name for entry in scandir(egg_link_contents))
            if name[-9:] == ".egg-info"
        )
    else:
        egg_info_fnames = ()

    if egg_info_fnames:
        if len(egg_info_fnames) != 1:
            raise CondaError(
                f"Expected exactly one `egg-info` directory in '{egg_link_contents}', via egg-link '{egg_link_file}'."
                f" Instead found: {egg_info_fnames}.  These are often left over from "
                "legacy operations that did not clean up correctly.  Please "
                "remove all but one of these."
            )

        egg_info_full_path = join(egg_link_contents, egg_info_fnames[0])

        if isdir(egg_info_full_path):
            egg_info_full_path = join(egg_info_full_path, "PKG-INFO")

    if egg_info_full_path is None:
        raise OSError(ENOENT, strerror(ENOENT), egg_link_contents)

    return egg_info_full_path


# See: https://bitbucket.org/pypa/distlib/src/34629e41cdff5c29429c7a4d1569ef5508b56929/distlib/util.py?at=default&fileviewer=file-view-default  # NOQA
# ------------------------------------------------------------------------------------------------
def parse_marker(marker_string):
    """
    Parse marker string and return a dictionary containing a marker expression.

    The dictionary will contain keys "op", "lhs" and "rhs" for non-terminals in
    the expression grammar, or strings. A string contained in quotes is to be
    interpreted as a literal string, and a string not contained in quotes is a
    variable (such as os_name).
    """

    def marker_var(remaining):
        # either identifier, or literal string
        m = IDENTIFIER.match(remaining)
        if m:
            result = m.groups()[0]
            remaining = remaining[m.end() :]
        elif not remaining:
            raise SyntaxError("unexpected end of input")
        else:
            q = remaining[0]
            if q not in "'\"":
                raise SyntaxError(f"invalid expression: {remaining}")
            oq = "'\"".replace(q, "")
            remaining = remaining[1:]
            parts = [q]
            while remaining:
                # either a string chunk, or oq, or q to terminate
                if remaining[0] == q:
                    break
                elif remaining[0] == oq:
                    parts.append(oq)
                    remaining = remaining[1:]
                else:
                    m = STRING_CHUNK.match(remaining)
                    if not m:
                        raise SyntaxError(f"error in string literal: {remaining}")
                    parts.append(m.groups()[0])
                    remaining = remaining[m.end() :]
            else:
                s = "".join(parts)
                raise SyntaxError(f"unterminated string: {s}")
            parts.append(q)
            result = "".join(parts)
            remaining = remaining[1:].lstrip()  # skip past closing quote
        return result, remaining

    def marker_expr(remaining):
        if remaining and remaining[0] == "(":
            result, remaining = marker(remaining[1:].lstrip())
            if remaining[0] != ")":
                raise SyntaxError(f"unterminated parenthesis: {remaining}")
            remaining = remaining[1:].lstrip()
        else:
            lhs, remaining = marker_var(remaining)
            while remaining:
                m = MARKER_OP.match(remaining)
                if not m:
                    break
                op = m.groups()[0]
                remaining = remaining[m.end() :]
                rhs, remaining = marker_var(remaining)
                lhs = {"op": op, "lhs": lhs, "rhs": rhs}
            result = lhs
        return result, remaining

    def marker_and(remaining):
        lhs, remaining = marker_expr(remaining)
        while remaining:
            m = AND.match(remaining)
            if not m:
                break
            remaining = remaining[m.end() :]
            rhs, remaining = marker_expr(remaining)
            lhs = {"op": "and", "lhs": lhs, "rhs": rhs}
        return lhs, remaining

    def marker(remaining):
        lhs, remaining = marker_and(remaining)
        while remaining:
            m = OR.match(remaining)
            if not m:
                break
            remaining = remaining[m.end() :]
            rhs, remaining = marker_and(remaining)
            lhs = {"op": "or", "lhs": lhs, "rhs": rhs}
        return lhs, remaining

    return marker(marker_string)


# See:
#   https://bitbucket.org/pypa/distlib/src/34629e41cdff5c29429c7a4d1569ef5508b56929/distlib/util.py?at=default&fileviewer=file-view-default  # NOQA
#   https://bitbucket.org/pypa/distlib/src/34629e41cdff5c29429c7a4d1569ef5508b56929/distlib/markers.py?at=default&fileviewer=file-view-default  # NOQA
# ------------------------------------------------------------------------------------------------
#
# Requirement parsing code as per PEP 508
#
IDENTIFIER = re.compile(r"^([\w\.-]+)\s*")
VERSION_IDENTIFIER = re.compile(r"^([\w\.*+-]+)\s*")
COMPARE_OP = re.compile(r"^(<=?|>=?|={2,3}|[~!]=)\s*")
MARKER_OP = re.compile(r"^((<=?)|(>=?)|={2,3}|[~!]=|in|not\s+in)\s*")
OR = re.compile(r"^or\b\s*")
AND = re.compile(r"^and\b\s*")
NON_SPACE = re.compile(r"(\S+)\s*")
STRING_CHUNK = re.compile(r"([\s\w\.{}()*+#:;,/?!~`@$%^&=|<>\[\]-]+)")


def _is_literal(o):
    if not isinstance(o, str) or not o:
        return False
    return o[0] in "'\""


class Evaluator:
    """This class is used to evaluate marker expressions."""

    operations = {
        "==": lambda x, y: x == y,
        "===": lambda x, y: x == y,
        "~=": lambda x, y: x == y or x > y,
        "!=": lambda x, y: x != y,
        "<": lambda x, y: x < y,
        "<=": lambda x, y: x == y or x < y,
        ">": lambda x, y: x > y,
        ">=": lambda x, y: x == y or x > y,
        "and": lambda x, y: x and y,
        "or": lambda x, y: x or y,
        "in": lambda x, y: x in y,
        "not in": lambda x, y: x not in y,
    }

    def evaluate(self, expr, context):
        """
        Evaluate a marker expression returned by the :func:`parse_requirement`
        function in the specified context.
        """
        if isinstance(expr, str):
            if expr[0] in "'\"":
                result = expr[1:-1]
            else:
                if expr not in context:
                    raise SyntaxError(f"unknown variable: {expr}")
                result = context[expr]
        else:
            assert isinstance(expr, dict)
            op = expr["op"]
            if op not in self.operations:
                raise NotImplementedError(f"op not implemented: {op}")
            elhs = expr["lhs"]
            erhs = expr["rhs"]
            if _is_literal(expr["lhs"]) and _is_literal(expr["rhs"]):
                raise SyntaxError(f"invalid comparison: {elhs} {op} {erhs}")

            lhs = self.evaluate(elhs, context)
            rhs = self.evaluate(erhs, context)
            result = self.operations[op](lhs, rhs)
        return result


# def update_marker_context(python_version):
#     """Update default marker context to include environment python version."""
#     updated_context = DEFAULT_MARKER_CONTEXT.copy()
#     context = {
#         'python_full_version': python_version,
#         'python_version': '.'.join(python_version.split('.')[:2]),
#         'extra': '',
#     }
#     updated_context.update(context)
#     return updated_context


def get_default_marker_context():
    """Return the default context dictionary to use when parsing markers."""

    def format_full_version(info):
        version = f"{info.major}.{info.minor}.{info.micro}"
        kind = info.releaselevel
        if kind != "final":
            version += kind[0] + str(info.serial)
        return version

    if hasattr(sys, "implementation"):
        implementation_version = format_full_version(sys.implementation.version)
        implementation_name = sys.implementation.name
    else:
        implementation_version = "0"
        implementation_name = ""

    # TODO: we can't use this
    result = {
        # See: https://www.python.org/dev/peps/pep-0508/#environment-markers
        "implementation_name": implementation_name,
        "implementation_version": implementation_version,
        "os_name": os_name,
        "platform_machine": platform.machine(),
        "platform_python_implementation": platform.python_implementation(),
        "platform_release": platform.release(),
        "platform_system": platform.system(),
        "platform_version": platform.version(),
        "python_full_version": platform.python_version(),
        "python_version": ".".join(platform.python_version().split(".")[:2]),
        "sys_platform": sys.platform,
        # See: https://www.python.org/dev/peps/pep-0345/#environment-markers
        "os.name": os_name,
        "platform.python_implementation": platform.python_implementation(),
        "platform.version": platform.version(),
        "platform.machine": platform.machine(),
        "sys.platform": sys.platform,
        "extra": "",
    }
    return result


DEFAULT_MARKER_CONTEXT = get_default_marker_context()
evaluator = Evaluator()


# FIXME: Should this raise errors, or fail silently or with a warning?
def interpret(marker, execution_context=None):
    """
    Interpret a marker and return a result depending on environment.

    :param marker: The marker to interpret.
    :type marker: str
    :param execution_context: The context used for name lookup.
    :type execution_context: mapping
    """
    try:
        expr, rest = parse_marker(marker)
    except Exception as e:
        raise SyntaxError(f"Unable to interpret marker syntax: {marker}: {e}")

    if rest and rest[0] != "#":
        raise SyntaxError(f"unexpected trailing data in marker: {marker}: {rest}")

    context = DEFAULT_MARKER_CONTEXT.copy()
    if execution_context:
        context.update(execution_context)

    return evaluator.evaluate(expr, context)
