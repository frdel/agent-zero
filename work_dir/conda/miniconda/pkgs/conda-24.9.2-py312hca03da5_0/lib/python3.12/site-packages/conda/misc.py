# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Miscellaneous utility functions."""

import os
import re
import shutil
import sys
from collections import defaultdict
from logging import getLogger
from os.path import abspath, dirname, exists, isdir, isfile, join, relpath
from typing import Iterable

from .base.context import context
from .common.compat import on_mac, on_win, open_utf8
from .common.io import dashlist
from .common.path import expand
from .common.url import is_url, join_url, path_to_url
from .core.index import get_index
from .core.link import PrefixSetup, UnlinkLinkTransaction
from .core.package_cache_data import PackageCacheData, ProgressiveFetchExtract
from .core.prefix_data import PrefixData
from .deprecations import deprecated
from .exceptions import (
    CondaExitZero,
    DisallowedPackageError,
    DryRunExit,
    PackagesNotFoundError,
    ParseError,
)
from .gateways.disk.delete import rm_rf
from .gateways.disk.link import islink, readlink, symlink
from .models.match_spec import ChannelMatch, MatchSpec
from .models.prefix_graph import PrefixGraph

log = getLogger(__name__)


def conda_installed_files(prefix, exclude_self_build=False):
    """
    Return the set of files which have been installed (using conda) into
    a given prefix.
    """
    res = set()
    for meta in PrefixData(prefix).iter_records():
        if exclude_self_build and "file_hash" in meta:
            continue
        res.update(set(meta.get("files", ())))
    return res


url_pat = re.compile(
    r"(?:(?P<url_p>.+)(?:[/\\]))?"
    r"(?P<fn>[^/\\#]+(?:\.tar\.bz2|\.conda))"
    r"(?:#("
    r"(?P<md5>[0-9a-f]{32})"
    r"|((sha256:)?(?P<sha256>[0-9a-f]{64}))"
    r"))?$"
)


def _match_specs_from_explicit(specs: Iterable[str]) -> Iterable[MatchSpec]:
    for spec in specs:
        if spec == "@EXPLICIT":
            continue

        if not is_url(spec):
            """
            # This does not work because url_to_path does not enforce Windows
            # backslashes. Should it? Seems like a dangerous change to make but
            # it would be cleaner.
            expanded = expand(spec)
            urled = path_to_url(expanded)
            pathed = url_to_path(urled)
            assert pathed == expanded
            """
            spec = path_to_url(expand(spec))

        # parse URL
        m = url_pat.match(spec)
        if m is None:
            raise ParseError(f"Could not parse explicit URL: {spec}")
        url_p, fn = m.group("url_p"), m.group("fn")
        url = join_url(url_p, fn)
        # url_p is everything but the tarball_basename and the checksum
        checksums = {}
        if md5 := m.group("md5"):
            checksums["md5"] = md5
        if sha256 := m.group("sha256"):
            checksums["sha256"] = sha256
        yield MatchSpec(url, **checksums)


@deprecated.argument("25.3", "25.9", "index_args")
def explicit(specs, prefix, verbose=False, force_extract=True, index=None):
    actions = defaultdict(list)
    actions["PREFIX"] = prefix

    fetch_specs = list(_match_specs_from_explicit(specs))

    if context.dry_run:
        raise DryRunExit()

    pfe = ProgressiveFetchExtract(fetch_specs)
    pfe.execute()

    if context.download_only:
        raise CondaExitZero(
            "Package caches prepared. "
            "UnlinkLinkTransaction cancelled with --download-only option."
        )

    # now make an UnlinkLinkTransaction with the PackageCacheRecords as inputs
    # need to add package name to fetch_specs so that history parsing keeps track of them correctly
    specs_pcrecs = tuple(
        [spec, next(PackageCacheData.query_all(spec), None)] for spec in fetch_specs
    )

    # Assert that every spec has a PackageCacheRecord
    specs_with_missing_pcrecs = [
        str(spec) for spec, pcrec in specs_pcrecs if pcrec is None
    ]
    if specs_with_missing_pcrecs:
        if len(specs_with_missing_pcrecs) == len(specs_pcrecs):
            raise AssertionError("No package cache records found")
        else:
            missing_precs_list = ", ".join(specs_with_missing_pcrecs)
            raise AssertionError(
                f"Missing package cache records for: {missing_precs_list}"
            )

    precs_to_remove = []
    prefix_data = PrefixData(prefix)
    for q, (spec, pcrec) in enumerate(specs_pcrecs):
        new_spec = MatchSpec(spec, name=pcrec.name)
        specs_pcrecs[q][0] = new_spec

        prec = prefix_data.get(pcrec.name, None)
        if prec:
            # If we've already got matching specifications, then don't bother re-linking it
            if next(prefix_data.query(new_spec), None):
                specs_pcrecs[q][0] = None
            else:
                precs_to_remove.append(prec)

    stp = PrefixSetup(
        prefix,
        precs_to_remove,
        tuple(sp[1] for sp in specs_pcrecs if sp[0]),
        (),
        tuple(sp[0] for sp in specs_pcrecs if sp[0]),
        (),
    )

    txn = UnlinkLinkTransaction(stp)
    if not context.json and not context.quiet:
        txn.print_transaction_summary()
    txn.execute()


def rel_path(prefix, path, windows_forward_slashes=True):
    res = path[len(prefix) + 1 :]
    if on_win and windows_forward_slashes:
        res = res.replace("\\", "/")
    return res


def walk_prefix(prefix, ignore_predefined_files=True, windows_forward_slashes=True):
    """Return the set of all files in a given prefix directory."""
    res = set()
    prefix = abspath(prefix)
    ignore = {
        "pkgs",
        "envs",
        "conda-bld",
        "conda-meta",
        ".conda_lock",
        "users",
        "LICENSE.txt",
        "info",
        "conda-recipes",
        ".index",
        ".unionfs",
        ".nonadmin",
    }
    binignore = {"conda", "activate", "deactivate"}
    if on_mac:
        ignore.update({"python.app", "Launcher.app"})
    for fn in (entry.name for entry in os.scandir(prefix)):
        if ignore_predefined_files and fn in ignore:
            continue
        if isfile(join(prefix, fn)):
            res.add(fn)
            continue
        for root, dirs, files in os.walk(join(prefix, fn)):
            should_ignore = ignore_predefined_files and root == join(prefix, "bin")
            for fn2 in files:
                if should_ignore and fn2 in binignore:
                    continue
                res.add(relpath(join(root, fn2), prefix))
            for dn in dirs:
                path = join(root, dn)
                if islink(path):
                    res.add(relpath(path, prefix))

    if on_win and windows_forward_slashes:
        return {path.replace("\\", "/") for path in res}
    else:
        return res


def untracked(prefix, exclude_self_build=False):
    """Return (the set) of all untracked files for a given prefix."""
    conda_files = conda_installed_files(prefix, exclude_self_build)
    return {
        path
        for path in walk_prefix(prefix) - conda_files
        if not (
            path.endswith("~")
            or on_mac
            and path.endswith(".DS_Store")
            or path.endswith(".pyc")
            and path[:-1] in conda_files
        )
    }


def touch_nonadmin(prefix):
    """Creates $PREFIX/.nonadmin if sys.prefix/.nonadmin exists (on Windows)."""
    if on_win and exists(join(context.root_prefix, ".nonadmin")):
        if not isdir(prefix):
            os.makedirs(prefix)
        with open_utf8(join(prefix, ".nonadmin"), "w") as fo:
            fo.write("")


def clone_env(prefix1, prefix2, verbose=True, quiet=False, index_args=None):
    """Clone existing prefix1 into new prefix2."""
    untracked_files = untracked(prefix1)

    # Discard conda, conda-env and any package that depends on them
    filter = {}
    found = True
    while found:
        found = False
        for prec in PrefixData(prefix1).iter_records():
            name = prec["name"]
            if name in filter:
                continue
            if name == "conda":
                filter["conda"] = prec
                found = True
                break
            if name == "conda-env":
                filter["conda-env"] = prec
                found = True
                break
            for dep in prec.combined_depends:
                if MatchSpec(dep).name in filter:
                    filter[name] = prec
                    found = True

    if filter:
        if not quiet:
            fh = sys.stderr if context.json else sys.stdout
            print(
                "The following packages cannot be cloned out of the root environment:",
                file=fh,
            )
            for prec in filter.values():
                print(" - " + prec.dist_str(), file=fh)
        drecs = {
            prec
            for prec in PrefixData(prefix1).iter_records()
            if prec["name"] not in filter
        }
    else:
        drecs = {prec for prec in PrefixData(prefix1).iter_records()}

    # Resolve URLs for packages that do not have URLs
    index = {}
    unknowns = [prec for prec in drecs if not prec.get("url")]
    notfound = []
    if unknowns:
        index_args = index_args or {}
        index = get_index(**index_args)

        for prec in unknowns:
            spec = MatchSpec(name=prec.name, version=prec.version, build=prec.build)
            precs = tuple(prec for prec in index.values() if spec.match(prec))
            if not precs:
                notfound.append(spec)
            elif len(precs) > 1:
                drecs.remove(prec)
                drecs.add(_get_best_prec_match(precs))
            else:
                drecs.remove(prec)
                drecs.add(precs[0])
    if notfound:
        raise PackagesNotFoundError(notfound)

    # Assemble the URL and channel list
    urls = {}
    for prec in drecs:
        urls[prec] = prec["url"]

    precs = tuple(PrefixGraph(urls).graph)
    urls = [urls[prec] for prec in precs]

    disallowed = tuple(MatchSpec(s) for s in context.disallowed_packages)
    for prec in precs:
        if any(d.match(prec) for d in disallowed):
            raise DisallowedPackageError(prec)

    if verbose:
        print("Packages: %d" % len(precs))
        print("Files: %d" % len(untracked_files))

    if context.dry_run:
        raise DryRunExit()

    for f in untracked_files:
        src = join(prefix1, f)
        dst = join(prefix2, f)
        dst_dir = dirname(dst)
        if islink(dst_dir) or isfile(dst_dir):
            rm_rf(dst_dir)
        if not isdir(dst_dir):
            os.makedirs(dst_dir)
        if islink(src):
            symlink(readlink(src), dst)
            continue

        try:
            with open_utf8(src, "rb") as fi:
                data = fi.read()
        except OSError:
            continue

        try:
            s = data.decode("utf-8")
            s = s.replace(prefix1, prefix2)
            data = s.encode("utf-8")
        except UnicodeDecodeError:  # data is binary
            pass

        with open_utf8(dst, "wb") as fo:
            fo.write(data)
        shutil.copystat(src, dst)

    actions = explicit(
        urls,
        prefix2,
        verbose=not quiet,
        index=index,
        force_extract=False,
    )
    return actions, untracked_files


def _get_best_prec_match(precs):
    assert precs
    for channel in context.channels:
        channel_matcher = ChannelMatch(channel)
        prec_matches = tuple(
            prec for prec in precs if channel_matcher.match(prec.channel.name)
        )
        if prec_matches:
            break
    else:
        prec_matches = precs
    log.warning("Multiple packages found: %s", dashlist(prec_matches))
    return prec_matches[0]
