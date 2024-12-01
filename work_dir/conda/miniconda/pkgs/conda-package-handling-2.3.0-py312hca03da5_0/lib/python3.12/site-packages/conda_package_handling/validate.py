from __future__ import annotations

import hashlib
import os
from itertools import chain
from pathlib import Path

from conda_package_streaming import package_streaming

from .utils import TemporaryDirectory


def validate_converted_files_match(
    src_file_or_folder, subject, reference_ext=""
):  # pragma: nocover
    # No longer used by conda-package-handling
    from .api import extract

    with TemporaryDirectory() as tmpdir:
        assert tmpdir is not None
        if os.path.isdir(src_file_or_folder):
            src_folder = src_file_or_folder
        else:
            extract(src_file_or_folder + reference_ext, dest_dir=os.path.join(tmpdir, "src"))
            src_folder = os.path.join(tmpdir, "src")

        converted_folder = os.path.join(tmpdir, "converted")
        extract(subject, dest_dir=converted_folder)

        missing_files = set()
        mismatch_size = set()
        for root, dirs, files in os.walk(src_folder):
            for f in files:
                absfile = os.path.join(root, f)
                rp = os.path.relpath(absfile, src_folder)
                destpath = os.path.join(converted_folder, rp)
                if not os.path.islink(destpath):
                    if not os.path.isfile(destpath):
                        missing_files.add(rp)
                    elif os.stat(absfile).st_size != os.stat(destpath).st_size:
                        mismatch_size.add(rp)
    return src_file_or_folder, missing_files, mismatch_size


def hash_fn():
    return hashlib.blake2b()


IGNORE_FIELDS = {
    "uid",
    "gid",
    "mtime",
    "uname",
    "gname",
    "chksum",
}  #: ignore if not strict


def validate_converted_files_match_streaming(
    src: str | Path, reference: str | Path, *, strict=True
):
    """
    Check that two .tar.bz2 or .conda files (either of src_file and
    reference_file can be either format) match exactly, down to the timestamps
    etc.

    Does not check outside of the info- and pkg- components of a .conda.
    (conda's metadata.json, which gives the version "2" of the format)

    If strict = True, also check for matching uid, gid, mtime, uname, gname.
    """
    source_set = {}
    reference_set = {}
    ignore_fields = {"chksum"} if strict else IGNORE_FIELDS

    def get_fileset(filename: str | Path):
        fileset = {}
        components = ["info", "pkg"] if os.fspath(filename).endswith(".conda") else ["pkg"]
        with open(filename, "rb") as conda_file:
            for component in components:
                for tar, member in package_streaming.stream_conda_component(
                    filename, conda_file, component
                ):
                    info = {k: v for k, v in member.get_info().items() if k not in ignore_fields}

                    if member.isfile():
                        hasher = hash_fn()
                        fd = tar.extractfile(member)
                        assert fd is not None
                        for block in iter(lambda: fd.read(1 << 18), b""):  # type: ignore
                            hasher.update(block)

                        info["digest"] = hasher.hexdigest()

                    fileset[info["name"]] = info

        return fileset

    source_set = get_fileset(src)
    reference_set = get_fileset(reference)

    missing = []
    mismatched = []

    if source_set != reference_set:
        for file in chain(source_set, reference_set):
            if not (file in source_set and file in reference_set):
                missing.append(file)
            elif source_set[file] != reference_set[file]:
                mismatched.append(file)

    return src, missing, mismatched
