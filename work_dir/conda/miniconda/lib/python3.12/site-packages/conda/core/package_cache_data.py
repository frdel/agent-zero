# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Tools for managing the package cache (previously downloaded packages)."""

from __future__ import annotations

import codecs
import os
from collections import defaultdict
from concurrent.futures import CancelledError, ThreadPoolExecutor, as_completed
from errno import EACCES, ENOENT, EPERM, EROFS
from functools import partial
from itertools import chain
from json import JSONDecodeError
from logging import getLogger
from os import scandir
from os.path import basename, dirname, getsize, join
from sys import platform
from tarfile import ReadError
from typing import TYPE_CHECKING

from .. import CondaError, CondaMultiError, conda_signal_handler
from ..auxlib.collection import first
from ..auxlib.decorators import memoizemethod
from ..auxlib.entity import ValidationError
from ..base.constants import (
    CONDA_PACKAGE_EXTENSION_V1,
    CONDA_PACKAGE_EXTENSION_V2,
    CONDA_PACKAGE_EXTENSIONS,
    PACKAGE_CACHE_MAGIC_FILE,
)
from ..base.context import context
from ..common.constants import NULL, TRACE
from ..common.io import IS_INTERACTIVE, ProgressBar, time_recorder
from ..common.iterators import groupby_to_dict as groupby
from ..common.path import expand, strip_pkg_extension, url_to_path
from ..common.signals import signal_handler
from ..common.url import path_to_url
from ..exceptions import NotWritableError, NoWritablePkgsDirError
from ..gateways.disk.create import (
    create_package_cache_directory,
    extract_tarball,
    write_as_json_to_file,
)
from ..gateways.disk.delete import rm_rf
from ..gateways.disk.read import (
    compute_sum,
    isdir,
    isfile,
    islink,
    read_index_json,
    read_index_json_from_tarball,
    read_repodata_json,
)
from ..gateways.disk.test import file_path_is_writable
from ..models.match_spec import MatchSpec
from ..models.records import PackageCacheRecord, PackageRecord
from ..utils import human_bytes
from .path_actions import CacheUrlAction, ExtractPackageAction

if TYPE_CHECKING:
    from concurrent.futures import Future
    from pathlib import Path

log = getLogger(__name__)

FileNotFoundError = IOError

try:
    from conda_package_handling.api import THREADSAFE_EXTRACT
except ImportError:
    THREADSAFE_EXTRACT = False
# On the machines we tested, extraction doesn't get any faster after 3 threads
EXTRACT_THREADS = min(os.cpu_count() or 1, 3) if THREADSAFE_EXTRACT else 1


class PackageCacheType(type):
    """This metaclass does basic caching of PackageCache instance objects."""

    def __call__(cls, pkgs_dir: str | os.PathLike | Path):
        if isinstance(pkgs_dir, PackageCacheData):
            return pkgs_dir
        elif (pkgs_dir := str(pkgs_dir)) in PackageCacheData._cache_:
            return PackageCacheData._cache_[pkgs_dir]
        else:
            package_cache_instance = super().__call__(pkgs_dir)
            PackageCacheData._cache_[pkgs_dir] = package_cache_instance
            return package_cache_instance


class PackageCacheData(metaclass=PackageCacheType):
    _cache_: dict[str, PackageCacheData] = {}

    def __init__(self, pkgs_dir):
        self.pkgs_dir = pkgs_dir
        self.__package_cache_records = None
        self.__is_writable = NULL

        self._urls_data = UrlsData(pkgs_dir)

    def insert(self, package_cache_record):
        meta = join(
            package_cache_record.extracted_package_dir, "info", "repodata_record.json"
        )
        write_as_json_to_file(meta, PackageRecord.from_objects(package_cache_record))

        self._package_cache_records[package_cache_record] = package_cache_record

    def load(self):
        self.__package_cache_records = _package_cache_records = {}
        self._check_writable()  # called here to create the cache if it doesn't exist
        if not isdir(self.pkgs_dir):
            # no directory exists, and we didn't have permissions to create it
            return

        _CONDA_TARBALL_EXTENSIONS = CONDA_PACKAGE_EXTENSIONS
        pkgs_dir_contents = tuple(entry.name for entry in scandir(self.pkgs_dir))
        for base_name in self._dedupe_pkgs_dir_contents(pkgs_dir_contents):
            full_path = join(self.pkgs_dir, base_name)
            if islink(full_path):
                continue
            elif (
                isdir(full_path)
                and isfile(join(full_path, "info", "index.json"))
                or isfile(full_path)
                and full_path.endswith(_CONDA_TARBALL_EXTENSIONS)
            ):
                try:
                    package_cache_record = self._make_single_record(base_name)
                except ValidationError as err:
                    # ValidationError: package fields are invalid
                    log.warning(
                        f"Failed to create package cache record for '{base_name}'. {err}"
                    )
                    package_cache_record = None

                # if package_cache_record is None, it means we couldn't create a record, ignore
                if package_cache_record:
                    _package_cache_records[package_cache_record] = package_cache_record

    def reload(self):
        self.load()
        return self

    def get(self, package_ref, default=NULL):
        assert isinstance(package_ref, PackageRecord)
        try:
            return self._package_cache_records[package_ref]
        except KeyError:
            if default is not NULL:
                return default
            else:
                raise

    def remove(self, package_ref, default=NULL):
        if default is NULL:
            return self._package_cache_records.pop(package_ref)
        else:
            return self._package_cache_records.pop(package_ref, default)

    def query(self, package_ref_or_match_spec):
        # returns a generator
        param = package_ref_or_match_spec
        if isinstance(param, str):
            param = MatchSpec(param)
        if isinstance(param, MatchSpec):
            return (
                pcrec
                for pcrec in self._package_cache_records.values()
                if param.match(pcrec)
            )
        else:
            assert isinstance(param, PackageRecord)
            return (
                pcrec
                for pcrec in self._package_cache_records.values()
                if pcrec == param
            )

    def iter_records(self):
        return iter(self._package_cache_records)

    @classmethod
    def query_all(cls, package_ref_or_match_spec, pkgs_dirs=None):
        if pkgs_dirs is None:
            pkgs_dirs = context.pkgs_dirs

        return chain.from_iterable(
            pcache.query(package_ref_or_match_spec)
            for pcache in cls.all_caches_writable_first(pkgs_dirs)
        )

    # ##########################################################################################
    # these class methods reach across all package cache directories (usually context.pkgs_dirs)
    # ##########################################################################################

    @classmethod
    def first_writable(cls, pkgs_dirs=None):
        # Calling this method will *create* a package cache directory if one does not already
        # exist. Any caller should intend to *use* that directory for *writing*, not just reading.
        if pkgs_dirs is None:
            pkgs_dirs = context.pkgs_dirs
        for pkgs_dir in pkgs_dirs:
            package_cache = cls(pkgs_dir)
            i_wri = package_cache.is_writable
            if i_wri is True:
                return package_cache
            elif i_wri is None:
                # means package cache directory doesn't exist, need to try to create it
                try:
                    created = create_package_cache_directory(package_cache.pkgs_dir)
                except NotWritableError:
                    continue
                if created:
                    package_cache.__is_writable = True
                    return package_cache

        raise NoWritablePkgsDirError(pkgs_dirs)

    @classmethod
    def writable_caches(cls, pkgs_dirs=None):
        if pkgs_dirs is None:
            pkgs_dirs = context.pkgs_dirs
        writable_caches = tuple(
            filter(lambda c: c.is_writable, (cls(pd) for pd in pkgs_dirs))
        )
        return writable_caches

    @classmethod
    def read_only_caches(cls, pkgs_dirs=None):
        if pkgs_dirs is None:
            pkgs_dirs = context.pkgs_dirs
        read_only_caches = tuple(
            filter(lambda c: not c.is_writable, (cls(pd) for pd in pkgs_dirs))
        )
        return read_only_caches

    @classmethod
    def all_caches_writable_first(cls, pkgs_dirs=None):
        if pkgs_dirs is None:
            pkgs_dirs = context.pkgs_dirs
        pc_groups = groupby(lambda pc: pc.is_writable, (cls(pd) for pd in pkgs_dirs))
        return (*pc_groups.get(True, ()), *pc_groups.get(False, ()))

    @classmethod
    def get_all_extracted_entries(cls):
        package_caches = (cls(pd) for pd in context.pkgs_dirs)
        return tuple(
            pc_entry
            for pc_entry in chain.from_iterable(
                package_cache.values() for package_cache in package_caches
            )
            if pc_entry.is_extracted
        )

    @classmethod
    def get_entry_to_link(cls, package_ref):
        pc_entry = next(
            (pcrec for pcrec in cls.query_all(package_ref) if pcrec.is_extracted), None
        )
        if pc_entry is not None:
            return pc_entry

        # this can happen with `conda install path/to/package.tar.bz2`
        #   because dist has channel '<unknown>'
        # if ProgressiveFetchExtract did its job correctly, what we're looking for
        #   should be the matching dist_name in the first writable package cache
        # we'll search all caches for a match, but search writable caches first
        dist_str = package_ref.dist_str().rsplit(":", 1)[-1]
        pc_entry = next(
            (
                cache._scan_for_dist_no_channel(dist_str)
                for cache in cls.all_caches_writable_first()
                if cache
            ),
            None,
        )
        if pc_entry is not None:
            return pc_entry
        raise CondaError(
            f"No package '{package_ref.dist_str()}' found in cache directories."
        )

    @classmethod
    def tarball_file_in_cache(cls, tarball_path, md5sum=None, exclude_caches=()):
        tarball_full_path, md5sum = cls._clean_tarball_path_and_get_md5sum(
            tarball_path, md5sum
        )
        pc_entry = first(
            cls(pkgs_dir).tarball_file_in_this_cache(tarball_full_path, md5sum)
            for pkgs_dir in context.pkgs_dirs
            if pkgs_dir not in exclude_caches
        )
        return pc_entry

    @classmethod
    def clear(cls):
        cls._cache_.clear()

    def tarball_file_in_this_cache(self, tarball_path, md5sum=None):
        tarball_full_path, md5sum = self._clean_tarball_path_and_get_md5sum(
            tarball_path, md5sum
        )
        tarball_basename = basename(tarball_full_path)
        pc_entry = first(
            (pc_entry for pc_entry in self.values()),
            key=lambda pce: pce.tarball_basename == tarball_basename
            and pce.md5 == md5sum,
        )
        return pc_entry

    @property
    def _package_cache_records(self):
        # don't actually populate _package_cache_records until we need it
        if self.__package_cache_records is None:
            self.load()
        return self.__package_cache_records

    @property
    def is_writable(self):
        # returns None if package cache directory does not exist / has not been created
        if self.__is_writable is NULL:
            return self._check_writable()
        return self.__is_writable

    def _check_writable(self):
        magic_file = join(self.pkgs_dir, PACKAGE_CACHE_MAGIC_FILE)
        if isfile(magic_file):
            i_wri = file_path_is_writable(join(self.pkgs_dir, PACKAGE_CACHE_MAGIC_FILE))
            self.__is_writable = i_wri
            log.debug("package cache directory '%s' writable: %s", self.pkgs_dir, i_wri)
        else:
            log.log(TRACE, "package cache directory '%s' does not exist", self.pkgs_dir)
            self.__is_writable = i_wri = None
        return i_wri

    @staticmethod
    def _clean_tarball_path_and_get_md5sum(tarball_path, md5sum=None):
        if tarball_path.startswith("file:/"):
            tarball_path = url_to_path(tarball_path)
        tarball_full_path = expand(tarball_path)

        if isfile(tarball_full_path) and md5sum is None:
            md5sum = compute_sum(tarball_full_path, "md5")

        return tarball_full_path, md5sum

    def _scan_for_dist_no_channel(self, dist_str):
        return next(
            (
                pcrec
                for pcrec in self._package_cache_records
                if pcrec.dist_str().rsplit(":", 1)[-1] == dist_str
            ),
            None,
        )

    def itervalues(self):
        return iter(self.values())

    def values(self):
        return self._package_cache_records.values()

    def __repr__(self):
        args = (f"{key}={getattr(self, key)!r}" for key in ("pkgs_dir",))
        return "{}({})".format(self.__class__.__name__, ", ".join(args))

    def _make_single_record(self, package_filename):
        # delay-load this to help make sure libarchive can be found
        from conda_package_handling.api import InvalidArchiveError

        package_tarball_full_path = join(self.pkgs_dir, package_filename)
        log.log(TRACE, "adding to package cache %s", package_tarball_full_path)
        extracted_package_dir, pkg_ext = strip_pkg_extension(package_tarball_full_path)

        # try reading info/repodata_record.json
        try:
            repodata_record = read_repodata_json(extracted_package_dir)
            package_cache_record = PackageCacheRecord.from_objects(
                repodata_record,
                package_tarball_full_path=package_tarball_full_path,
                extracted_package_dir=extracted_package_dir,
            )
            return package_cache_record
        except (OSError, JSONDecodeError, ValueError, FileNotFoundError) as e:
            # EnvironmentError if info/repodata_record.json doesn't exists
            # JsonDecodeError if info/repodata_record.json is partially extracted or corrupted
            #   python 2.7 raises ValueError instead of JsonDecodeError
            #   ValueError("No JSON object could be decoded")
            log.debug(
                "unable to read %s\n  because %r",
                join(extracted_package_dir, "info", "repodata_record.json"),
                e,
            )

            # try reading info/index.json
            try:
                raw_json_record = read_index_json(extracted_package_dir)
            except (OSError, JSONDecodeError, ValueError, FileNotFoundError) as e:
                # EnvironmentError if info/index.json doesn't exist
                # JsonDecodeError if info/index.json is partially extracted or corrupted
                #   python 2.7 raises ValueError instead of JsonDecodeError
                #   ValueError("No JSON object could be decoded")
                log.debug(
                    "unable to read %s\n  because %r",
                    join(extracted_package_dir, "info", "index.json"),
                    e,
                )

                if isdir(extracted_package_dir) and not isfile(
                    package_tarball_full_path
                ):
                    # We have a directory that looks like a conda package, but without
                    # (1) info/repodata_record.json or info/index.json, and (2) a conda package
                    # tarball, there's not much we can do.  We'll just ignore it.
                    return None

                try:
                    if self.is_writable:
                        if isdir(extracted_package_dir):
                            # We have a partially unpacked conda package directory. Best thing
                            # to do is remove it and try extracting.
                            rm_rf(extracted_package_dir)
                        try:
                            extract_tarball(
                                package_tarball_full_path, extracted_package_dir
                            )
                        except (OSError, InvalidArchiveError) as e:
                            if e.errno == ENOENT:
                                # FileNotFoundError(2, 'No such file or directory')
                                # At this point, we can assume the package tarball is bad.
                                # Remove everything and move on.
                                # see https://github.com/conda/conda/issues/6707
                                rm_rf(package_tarball_full_path)
                                rm_rf(extracted_package_dir)
                                return None
                        try:
                            raw_json_record = read_index_json(extracted_package_dir)
                        except (OSError, JSONDecodeError, FileNotFoundError):
                            # At this point, we can assume the package tarball is bad.
                            # Remove everything and move on.
                            rm_rf(package_tarball_full_path)
                            rm_rf(extracted_package_dir)
                            return None
                    else:
                        raw_json_record = read_index_json_from_tarball(
                            package_tarball_full_path
                        )
                except (
                    EOFError,
                    ReadError,
                    FileNotFoundError,
                    InvalidArchiveError,
                ) as e:
                    # EOFError: Compressed file ended before the end-of-stream marker was reached
                    # tarfile.ReadError: file could not be opened successfully
                    # We have a corrupted tarball. Remove the tarball so it doesn't affect
                    # anything, and move on.
                    log.debug(
                        "unable to extract info/index.json from %s\n  because %r",
                        package_tarball_full_path,
                        e,
                    )
                    rm_rf(package_tarball_full_path)
                    return None

            # we were able to read info/index.json, so let's continue
            if isfile(package_tarball_full_path):
                md5 = compute_sum(package_tarball_full_path, "md5")
            else:
                md5 = None

            url = self._urls_data.get_url(package_filename)
            package_cache_record = PackageCacheRecord.from_objects(
                raw_json_record,
                url=url,
                fn=basename(package_tarball_full_path),
                md5=md5,
                size=getsize(package_tarball_full_path),
                package_tarball_full_path=package_tarball_full_path,
                extracted_package_dir=extracted_package_dir,
            )

            # write the info/repodata_record.json file so we can short-circuit this next time
            if self.is_writable:
                repodata_record = PackageRecord.from_objects(package_cache_record)
                repodata_record_path = join(
                    extracted_package_dir, "info", "repodata_record.json"
                )
                try:
                    write_as_json_to_file(repodata_record_path, repodata_record)
                except OSError as e:
                    if e.errno in (EACCES, EPERM, EROFS) and isdir(
                        dirname(repodata_record_path)
                    ):
                        raise NotWritableError(
                            repodata_record_path, e.errno, caused_by=e
                        )
                    else:
                        raise

            return package_cache_record

    @staticmethod
    def _dedupe_pkgs_dir_contents(pkgs_dir_contents):
        # if both 'six-1.10.0-py35_0/' and 'six-1.10.0-py35_0.tar.bz2' are in pkgs_dir,
        #   only 'six-1.10.0-py35_0.tar.bz2' will be in the return contents
        if not pkgs_dir_contents:
            return []
        _CONDA_TARBALL_EXTENSION_V1 = CONDA_PACKAGE_EXTENSION_V1
        _CONDA_TARBALL_EXTENSION_V2 = CONDA_PACKAGE_EXTENSION_V2
        _strip_pkg_extension = strip_pkg_extension
        groups = defaultdict(set)
        any(
            groups[ext].add(fn_root)
            for fn_root, ext in (_strip_pkg_extension(fn) for fn in pkgs_dir_contents)
        )
        conda_extensions = groups[_CONDA_TARBALL_EXTENSION_V2]
        tar_bz2_extensions = groups[_CONDA_TARBALL_EXTENSION_V1] - conda_extensions
        others = groups[None] - conda_extensions - tar_bz2_extensions
        return sorted(
            (
                *(path + _CONDA_TARBALL_EXTENSION_V2 for path in conda_extensions),
                *(path + _CONDA_TARBALL_EXTENSION_V1 for path in tar_bz2_extensions),
                *others,
            )
        )


class UrlsData:
    # this is a class to manage urls.txt
    # it should basically be thought of as a sequence
    # in this class I'm breaking the rule that all disk access goes through conda.gateways

    def __init__(self, pkgs_dir):
        self.pkgs_dir = pkgs_dir
        self.urls_txt_path = urls_txt_path = join(pkgs_dir, "urls.txt")
        if isfile(urls_txt_path):
            with open(urls_txt_path, "rb") as fh:
                self._urls_data = [line.strip().decode("utf-8") for line in fh]
                self._urls_data.reverse()
        else:
            self._urls_data = []

    def __contains__(self, url):
        return url in self._urls_data

    def __iter__(self):
        return iter(self._urls_data)

    def add_url(self, url):
        with codecs.open(self.urls_txt_path, mode="ab", encoding="utf-8") as fh:
            linefeed = "\r\n" if platform == "win32" else "\n"
            fh.write(url + linefeed)
        self._urls_data.insert(0, url)

    @memoizemethod
    def get_url(self, package_path):
        # package path can be a full path or just a basename
        #   can be either an extracted directory or tarball
        package_path = basename(package_path)
        # NOTE: This makes an assumption that all extensionless packages came from a .tar.bz2.
        #       That's probably a good assumption going forward, because we should now always
        #       be recording the extension in urls.txt.  The extensionless situation should be
        #       legacy behavior only.
        if not package_path.endswith(CONDA_PACKAGE_EXTENSIONS):
            package_path += CONDA_PACKAGE_EXTENSION_V1
        return first(self, lambda url: basename(url) == package_path)


# ##############################
# downloading
# ##############################


class ProgressiveFetchExtract:
    @staticmethod
    def make_actions_for_record(pref_or_spec):
        assert pref_or_spec is not None
        # returns a cache_action and extract_action

        # if the pref or spec has an md5 value
        # look in all caches for package cache record that is
        #   (1) already extracted, and
        #   (2) matches the md5
        # If one exists, no actions are needed.
        sha256 = pref_or_spec.get("sha256")
        size = pref_or_spec.get("size")
        md5 = pref_or_spec.get("md5")
        legacy_bz2_size = pref_or_spec.get("legacy_bz2_size")
        legacy_bz2_md5 = pref_or_spec.get("legacy_bz2_md5")

        def pcrec_matches(pcrec):
            matches = True
            # sha256 is overkill for things that are already in the package cache.
            #     It's just a quick match.
            # if sha256 is not None and pcrec.sha256 is not None:
            #     matches = sha256 == pcrec.sha256
            if size is not None and pcrec.get("size") is not None:
                matches = pcrec.size in (size, legacy_bz2_size)
            if matches and md5 is not None and pcrec.get("md5") is not None:
                matches = pcrec.md5 in (md5, legacy_bz2_md5)
            return matches

        extracted_pcrec = next(
            (
                pcrec
                for pcrec in chain.from_iterable(
                    PackageCacheData(pkgs_dir).query(pref_or_spec)
                    for pkgs_dir in context.pkgs_dirs
                )
                if pcrec.is_extracted
            ),
            None,
        )
        if (
            extracted_pcrec
            and pcrec_matches(extracted_pcrec)
            and extracted_pcrec.get("url")
        ):
            return None, None

        # there is no extracted dist that can work, so now we look for tarballs that
        #   aren't extracted
        # first we look in all writable caches, and if we find a match, we extract in place
        # otherwise, if we find a match in a non-writable cache, we link it to the first writable
        #   cache, and then extract
        pcrec_from_writable_cache = next(
            (
                pcrec
                for pcrec in chain.from_iterable(
                    pcache.query(pref_or_spec)
                    for pcache in PackageCacheData.writable_caches()
                )
                if pcrec.is_fetched
            ),
            None,
        )
        if (
            pcrec_from_writable_cache
            and pcrec_matches(pcrec_from_writable_cache)
            and pcrec_from_writable_cache.get("url")
        ):
            # extract in place
            extract_action = ExtractPackageAction(
                source_full_path=pcrec_from_writable_cache.package_tarball_full_path,
                target_pkgs_dir=dirname(
                    pcrec_from_writable_cache.package_tarball_full_path
                ),
                target_extracted_dirname=basename(
                    pcrec_from_writable_cache.extracted_package_dir
                ),
                record_or_spec=pcrec_from_writable_cache,
                sha256=pcrec_from_writable_cache.sha256 or sha256,
                size=pcrec_from_writable_cache.size or size,
                md5=pcrec_from_writable_cache.md5 or md5,
            )
            return None, extract_action

        pcrec_from_read_only_cache = next(
            (
                pcrec
                for pcrec in chain.from_iterable(
                    pcache.query(pref_or_spec)
                    for pcache in PackageCacheData.read_only_caches()
                )
                if pcrec.is_fetched
            ),
            None,
        )

        first_writable_cache = PackageCacheData.first_writable()
        if pcrec_from_read_only_cache and pcrec_matches(pcrec_from_read_only_cache):
            # we found a tarball, but it's in a read-only package cache
            # we need to link the tarball into the first writable package cache,
            #   and then extract
            cache_action = CacheUrlAction(
                url=path_to_url(pcrec_from_read_only_cache.package_tarball_full_path),
                target_pkgs_dir=first_writable_cache.pkgs_dir,
                target_package_basename=pcrec_from_read_only_cache.fn,
                sha256=pcrec_from_read_only_cache.get("sha256") or sha256,
                size=pcrec_from_read_only_cache.get("size") or size,
                md5=pcrec_from_read_only_cache.get("md5") or md5,
            )
            trgt_extracted_dirname = strip_pkg_extension(pcrec_from_read_only_cache.fn)[
                0
            ]
            extract_action = ExtractPackageAction(
                source_full_path=cache_action.target_full_path,
                target_pkgs_dir=first_writable_cache.pkgs_dir,
                target_extracted_dirname=trgt_extracted_dirname,
                record_or_spec=pcrec_from_read_only_cache,
                sha256=pcrec_from_read_only_cache.get("sha256") or sha256,
                size=pcrec_from_read_only_cache.get("size") or size,
                md5=pcrec_from_read_only_cache.get("md5") or md5,
            )
            return cache_action, extract_action

        # if we got here, we couldn't find a matching package in the caches
        #   we'll have to download one; fetch and extract
        url = pref_or_spec.get("url")
        assert url

        cache_action = CacheUrlAction(
            url=url,
            target_pkgs_dir=first_writable_cache.pkgs_dir,
            target_package_basename=pref_or_spec.fn,
            sha256=sha256,
            size=size,
            md5=md5,
        )
        extract_action = ExtractPackageAction(
            source_full_path=cache_action.target_full_path,
            target_pkgs_dir=first_writable_cache.pkgs_dir,
            target_extracted_dirname=strip_pkg_extension(pref_or_spec.fn)[0],
            record_or_spec=pref_or_spec,
            sha256=sha256,
            size=size,
            md5=md5,
        )
        return cache_action, extract_action

    def __init__(self, link_prefs):
        """
        Args:
            link_prefs (tuple[PackageRecord]):
                A sequence of :class:`PackageRecord`s to ensure available in a known
                package cache, typically for a follow-on :class:`UnlinkLinkTransaction`.
                Here, "available" means the package tarball is both downloaded and extracted
                to a package directory.
        """
        self.link_precs = link_prefs

        log.debug(
            "instantiating ProgressiveFetchExtract with\n  %s\n",
            "\n  ".join(pkg_rec.dist_str() for pkg_rec in link_prefs),
        )

        self.paired_actions = {}  # Map[pref, Tuple(CacheUrlAction, ExtractPackageAction)]

        self._prepared = False
        self._executed = False

    @time_recorder("fetch_extract_prepare")
    def prepare(self):
        if self._prepared:
            return

        # Download largest first
        def by_size(prec: PackageRecord | MatchSpec):
            # the test suite passes MatchSpec in here, is that an intentional
            # feature?
            try:
                return int(prec.size)  # type: ignore
            except (LookupError, ValueError, AttributeError):
                return 0

        largest_first = sorted(self.link_precs, key=by_size, reverse=True)

        self.paired_actions.update(
            (prec, self.make_actions_for_record(prec)) for prec in largest_first
        )
        self._prepared = True

    @property
    def cache_actions(self):
        return tuple(axns[0] for axns in self.paired_actions.values() if axns[0])

    @property
    def extract_actions(self):
        return tuple(axns[1] for axns in self.paired_actions.values() if axns[1])

    def execute(self):
        """
        Run each action in self.paired_actions. Each action in cache_actions
        runs before its corresponding extract_actions.
        """
        if self._executed:
            return
        if not self._prepared:
            self.prepare()

        assert not context.dry_run

        if not self.paired_actions:
            return

        if not context.verbose and not context.quiet and not context.json:
            print(
                "\nDownloading and Extracting Packages:",
                end="\n" if IS_INTERACTIVE else " ...working...",
            )
        else:
            log.debug(
                "prepared package cache actions:\n"
                "  cache_actions:\n"
                "    %s\n"
                "  extract_actions:\n"
                "    %s\n",
                "\n    ".join(str(ca) for ca in self.cache_actions),
                "\n    ".join(str(ea) for ea in self.extract_actions),
            )

        exceptions = []
        progress_bars = {}
        futures: list[Future] = []

        cancelled_flag = False

        def cancelled():
            """
            Used to cancel download threads.
            """
            nonlocal cancelled_flag
            return cancelled_flag

        with signal_handler(conda_signal_handler), time_recorder(
            "fetch_extract_execute"
        ), ThreadPoolExecutor(
            context.fetch_threads
        ) as fetch_executor, ThreadPoolExecutor(EXTRACT_THREADS) as extract_executor:
            for prec_or_spec, (
                cache_action,
                extract_action,
            ) in self.paired_actions.items():
                if cache_action is None and extract_action is None:
                    # Not sure when this is reached.
                    continue

                progress_bar = self._progress_bar(prec_or_spec, leave=False)

                progress_bars[prec_or_spec] = progress_bar

                future = fetch_executor.submit(
                    do_cache_action,
                    prec_or_spec,
                    cache_action,
                    progress_bar,
                    cancelled=cancelled,
                )

                future.add_done_callback(
                    partial(
                        done_callback,
                        actions=(cache_action,),
                        exceptions=exceptions,
                        progress_bar=progress_bar,
                        finish=False,
                    )
                )
                futures.append(future)

            try:
                for completed_future in as_completed(futures):
                    futures.remove(completed_future)
                    prec_or_spec = completed_future.result()

                    cache_action, extract_action = self.paired_actions[prec_or_spec]
                    extract_future = extract_executor.submit(
                        do_extract_action,
                        prec_or_spec,
                        extract_action,
                        progress_bars[prec_or_spec],
                    )
                    extract_future.add_done_callback(
                        partial(
                            done_callback,
                            actions=(cache_action, extract_action),
                            exceptions=exceptions,
                            progress_bar=progress_bars[prec_or_spec],
                            finish=True,
                        )
                    )
            except BaseException as e:
                # We are interested in KeyboardInterrupt delivered to
                # as_completed() while waiting, or any exception raised from
                # completed_future.result(). cancelled_flag is checked in the
                # progress callback to stop running transfers, shutdown() should
                # prevent new downloads from starting.
                cancelled_flag = True
                for future in futures:  # needed on top of .shutdown()
                    future.cancel()
                # Has a Python >=3.9 cancel_futures= parameter that does not
                # replace the above loop:
                fetch_executor.shutdown(wait=False)
                exceptions.append(e)

        for bar in progress_bars.values():
            bar.close()

        if not context.verbose and not context.quiet and not context.json:
            if IS_INTERACTIVE:
                print("\r")  # move to column 0
            else:
                print(" done")

        if exceptions:
            # avoid printing one CancelledError() per pending download
            not_cancelled = [e for e in exceptions if not isinstance(e, CancelledError)]
            raise CondaMultiError(not_cancelled)

        self._executed = True

    @staticmethod
    def _progress_bar(prec_or_spec, position=None, leave=False) -> ProgressBar:
        desc = ""
        if prec_or_spec.name and prec_or_spec.version:
            desc = "{}-{}".format(prec_or_spec.name or "", prec_or_spec.version or "")
        size = getattr(prec_or_spec, "size", None)
        size_str = size and human_bytes(size) or ""
        if len(desc) > 0:
            desc = "%-20.20s | " % desc
        if len(size_str) > 0:
            desc += "%-9s | " % size_str

        progress_bar = ProgressBar(
            desc,
            not context.verbose and not context.quiet and IS_INTERACTIVE,
            context.json,
            position=position,
            leave=leave,
        )

        return progress_bar

    def __hash__(self):
        return hash(self.link_precs)

    def __eq__(self, other):
        return hash(self) == hash(other)


def do_cache_action(prec, cache_action, progress_bar, download_total=1.0, *, cancelled):
    """This function gets called from `ProgressiveFetchExtract.execute`."""
    # pass None if already cached (simplifies code)
    if not cache_action:
        return prec
    cache_action.verify()

    if not cache_action.url.startswith("file:/"):

        def progress_update_cache_action(pct_completed):
            if cancelled():
                """
                Used to cancel dowload threads when parent thread is interrupted.
                """
                raise CancelledError()
            progress_bar.update_to(pct_completed * download_total)

    else:
        download_total = 0
        progress_update_cache_action = None

    cache_action.execute(progress_update_cache_action)
    return prec


def do_extract_action(prec, extract_action, progress_bar):
    """This function gets called after do_cache_action completes."""
    # pass None if already extracted (simplifies code)
    if not extract_action:
        return prec
    extract_action.verify()
    # currently unable to do updates on extract;
    # likely too fast to bother
    extract_action.execute(None)
    progress_bar.update_to(1.0)
    return prec


def do_cleanup(actions):
    for action in actions:
        if action:
            action.cleanup()


def do_reverse(actions):
    for action in actions:
        if action:
            action.reverse()


def done_callback(
    future: Future,
    actions: tuple[CacheUrlAction | ExtractPackageAction, ...],
    progress_bar: ProgressBar,
    exceptions: list[Exception],
    finish: bool = False,
):
    try:
        future.result()
    except Exception as e:
        # if it was interrupted with CTRL-C this might be BaseException and not
        # get caught here, but conda's signal handler also converts that to
        # CondaError which is just Exception.
        do_reverse(reversed(actions))
        exceptions.append(e)
    else:
        do_cleanup(actions)
        if finish:
            progress_bar.finish()
            progress_bar.refresh()
