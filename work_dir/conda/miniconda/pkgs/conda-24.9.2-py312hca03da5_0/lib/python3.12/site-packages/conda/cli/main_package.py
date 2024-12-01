# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""CLI implementation for `conda package`.

Provides some low-level tools for creating conda packages.
"""

import hashlib
import json
import os
import re
import tarfile
import tempfile
from argparse import ArgumentParser, Namespace, _SubParsersAction
from os.path import abspath, basename, dirname, isdir, isfile, islink, join


def configure_parser(sub_parsers: _SubParsersAction, **kwargs) -> ArgumentParser:
    from .helpers import add_parser_prefix

    summary = "Create low-level conda packages. (EXPERIMENTAL)"
    description = summary
    epilog = ""

    p = sub_parsers.add_parser(
        "package",
        help=summary,
        description=description,
        epilog=epilog,
        **kwargs,
    )
    add_parser_prefix(p)
    p.add_argument(
        "-w",
        "--which",
        metavar="PATH",
        nargs="+",
        action="store",
        help="Given some file's PATH, print which conda package the file came from.",
    )
    p.add_argument(
        "-r",
        "--reset",
        action="store_true",
        help="Remove all untracked files and exit.",
    )
    p.add_argument(
        "-u",
        "--untracked",
        action="store_true",
        help="Display all untracked files and exit.",
    )
    p.add_argument(
        "--pkg-name",
        action="store",
        default="unknown",
        help="Designate package name of the package being created.",
    )
    p.add_argument(
        "--pkg-version",
        action="store",
        default="0.0",
        help="Designate package version of the package being created.",
    )
    p.add_argument(
        "--pkg-build",
        action="store",
        default=0,
        help="Designate package build number of the package being created.",
    )
    p.set_defaults(func="conda.cli.main_package.execute")

    return p


def remove(prefix, files):
    """Remove files for a given prefix."""
    dst_dirs = set()
    for f in files:
        dst = join(prefix, f)
        dst_dirs.add(dirname(dst))
        os.unlink(dst)

    for path in sorted(dst_dirs, key=len, reverse=True):
        try:
            os.rmdir(path)
        except OSError:  # directory might not be empty
            pass


def execute(args: Namespace, parser: ArgumentParser) -> int:
    from ..base.context import context
    from ..misc import untracked

    prefix = context.target_prefix

    if args.which:
        for path in args.which:
            for prec in which_package(path):
                print("%-50s  %s" % (path, prec.dist_str()))
        return 0

    print("# prefix:", prefix)

    if args.reset:
        remove(prefix, untracked(prefix))
        return 0

    if args.untracked:
        files = sorted(untracked(prefix))
        print("# untracked files: %d" % len(files))
        for fn in files:
            print(fn)
        return 0

    make_tarbz2(
        prefix,
        name=args.pkg_name.lower(),
        version=args.pkg_version,
        build_number=int(args.pkg_build),
    )
    return 0


def get_installed_version(prefix, name):
    from ..core.prefix_data import PrefixData

    for info in PrefixData(prefix).iter_records():
        if info["name"] == name:
            return str(info["version"])
    return None


def create_info(name, version, build_number, requires_py):
    from ..base.context import context

    d = dict(
        name=name,
        version=version,
        platform=context.platform,
        arch=context.arch_name,
        build_number=int(build_number),
        build=str(build_number),
        depends=[],
    )
    if requires_py:
        d["build"] = ("py%d%d_" % requires_py) + d["build"]
        d["depends"].append("python %d.%d*" % requires_py)
    return d


shebang_pat = re.compile(r"^#!.+$", re.M)


def fix_shebang(tmp_dir, path):
    from ..base.constants import PREFIX_PLACEHOLDER

    if open(path, "rb").read(2) != "#!":
        return False

    with open(path) as fi:
        data = fi.read()
    m = shebang_pat.match(data)
    if not (m and "python" in m.group()):
        return False

    data = shebang_pat.sub(f"#!{PREFIX_PLACEHOLDER}/bin/python", data, count=1)
    tmp_path = join(tmp_dir, basename(path))
    with open(tmp_path, "w") as fo:
        fo.write(data)
    os.chmod(tmp_path, int("755", 8))
    return True


def _add_info_dir(t, tmp_dir, files, has_prefix, info):
    from ..auxlib.entity import EntityEncoder

    info_dir = join(tmp_dir, "info")
    os.mkdir(info_dir)
    with open(join(info_dir, "files"), "w") as fo:
        for f in files:
            fo.write(f + "\n")

    with open(join(info_dir, "index.json"), "w") as fo:
        json.dump(info, fo, indent=2, sort_keys=True, cls=EntityEncoder)

    if has_prefix:
        with open(join(info_dir, "has_prefix"), "w") as fo:
            for f in has_prefix:
                fo.write(f + "\n")

    for fn in os.listdir(info_dir):
        t.add(join(info_dir, fn), "info/" + fn)


def create_conda_pkg(prefix, files, info, tar_path, update_info=None):
    """Create a conda package and return a list of warnings."""
    from ..gateways.disk.delete import rmtree

    files = sorted(files)
    warnings = []
    has_prefix = []
    tmp_dir = tempfile.mkdtemp()
    t = tarfile.open(tar_path, "w:bz2")
    h = hashlib.new("sha1")
    for f in files:
        assert not (f.startswith("/") or f.endswith("/") or "\\" in f or f == ""), f
        path = join(prefix, f)
        if f.startswith("bin/") and fix_shebang(tmp_dir, path):
            path = join(tmp_dir, basename(path))
            has_prefix.append(f)
        t.add(path, f)
        h.update(f.encode("utf-8"))
        h.update(b"\x00")
        if islink(path):
            link = os.readlink(path)
            if isinstance(link, str):
                h.update(bytes(link, "utf-8"))
            else:
                h.update(link)
            if link.startswith("/"):
                warnings.append(f"found symlink to absolute path: {f} -> {link}")
        elif isfile(path):
            h.update(open(path, "rb").read())
            if path.endswith(".egg-link"):
                warnings.append(f"found egg link: {f}")

    info["file_hash"] = h.hexdigest()
    if update_info:
        update_info(info)
    _add_info_dir(t, tmp_dir, files, has_prefix, info)
    t.close()
    rmtree(tmp_dir)
    return warnings


def make_tarbz2(prefix, name="unknown", version="0.0", build_number=0, files=None):
    from ..base.constants import CONDA_PACKAGE_EXTENSION_V1
    from ..misc import untracked

    if files is None:
        files = untracked(prefix)
    print("# files: %d" % len(files))
    if len(files) == 0:
        print("# failed: nothing to do")
        return None

    if any("/site-packages/" in f for f in files):
        python_version = get_installed_version(prefix, "python")
        assert python_version is not None
        requires_py = tuple(int(x) for x in python_version[:3].split("."))
    else:
        requires_py = False

    info = create_info(name, version, build_number, requires_py)
    tarbz2_fn = ("{name}-{version}-{build}".format(**info)) + CONDA_PACKAGE_EXTENSION_V1
    create_conda_pkg(prefix, files, info, tarbz2_fn)
    print("# success")
    print(tarbz2_fn)
    return tarbz2_fn


def which_package(path):
    """Return the package containing the path.

    Provided the path of a (presumably) conda installed file, iterate over
    the conda packages the file came from. Usually the iteration yields
    only one package.
    """
    from ..common.path import paths_equal
    from ..core.prefix_data import PrefixData

    path = abspath(path)
    prefix = which_prefix(path)
    if prefix is None:
        from ..exceptions import CondaVerificationError

        raise CondaVerificationError(f"could not determine conda prefix from: {path}")

    for prec in PrefixData(prefix).iter_records():
        if any(paths_equal(join(prefix, f), path) for f in prec["files"] or ()):
            yield prec


def which_prefix(path):
    """Return the prefix for the provided path.

    Provided the path of a (presumably) conda installed file, return the
    environment prefix in which the file in located.
    """
    prefix = abspath(path)
    while True:
        if isdir(join(prefix, "conda-meta")):
            # we found the it, so let's return it
            return prefix
        if prefix == dirname(prefix):
            # we cannot chop off any more directories, so we didn't find it
            return None
        prefix = dirname(prefix)
