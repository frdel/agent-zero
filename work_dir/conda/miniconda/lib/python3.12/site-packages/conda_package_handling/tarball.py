import logging
import os
import re
import tarfile

from . import streaming, utils
from .interface import AbstractBaseFormat

LOG = logging.getLogger(__name__)


def _sort_file_order(prefix, files):
    """Sort by filesize, to optimize compression?"""
    info_slash = "info" + os.path.sep

    def order(f):
        # we don't care about empty files so send them back via 100000
        fsize = os.lstat(os.path.join(prefix, f)).st_size or 100000
        # info/* records will be False == 0, others will be 1.
        info_order = int(not f.startswith(info_slash))
        if info_order:
            _, ext = os.path.splitext(f)
            # Strip any .dylib.* and .so.* and rename .dylib to .so
            ext = re.sub(r"(\.dylib|\.so).*$", r".so", ext)
            if not ext:
                # Files without extensions should be sorted by dirname
                info_order = 1 + hash(os.path.dirname(f)) % (10**8)
            else:
                info_order = 1 + abs(hash(ext)) % (10**8)
        return info_order, fsize

    files_list = list(sorted(files, key=order))

    return files_list


def _create_no_libarchive(fullpath, files):
    with tarfile.open(fullpath, "w:bz2") as t:
        for f in files:
            t.add(f, filter=utils.anonymize_tarinfo)


def create_compressed_tarball(
    prefix, files, tmpdir, basename, ext, compression_filter, filter_opts=""
):
    tmp_path = os.path.join(tmpdir, basename)
    files = _sort_file_order(prefix, files)

    # add files in order of a) in info directory, b) increasing size so
    # we can access small manifest or json files without decompressing
    # possible large binary or data files
    fullpath = tmp_path + ext
    with utils.tmp_chdir(prefix):
        _create_no_libarchive(fullpath, files)
    return fullpath


class CondaTarBZ2(AbstractBaseFormat):
    @staticmethod
    def supported(fn):
        return fn.endswith(".tar.bz2")

    @staticmethod
    def extract(fn, dest_dir, **kw):
        if not os.path.isdir(dest_dir):
            os.makedirs(dest_dir)
        if not os.path.isabs(fn):
            fn = os.path.normpath(os.path.join(os.getcwd(), fn))

        streaming._extract(str(fn), str(dest_dir), components=["pkg"])

    @staticmethod
    def create(prefix, file_list, out_fn, out_folder=None, **kw):
        if out_folder is None:
            out_folder = os.getcwd()
        if os.path.isabs(out_fn):
            out_folder = os.path.dirname(out_fn)
        out_file = create_compressed_tarball(
            prefix,
            file_list,
            out_folder,
            os.path.basename(out_fn).replace(".tar.bz2", ""),
            ".tar.bz2",
            "bzip2",
        )
        return out_file

    @staticmethod
    def get_pkg_details(in_file):
        stat_result = os.stat(in_file)
        size = stat_result.st_size
        md5, sha256 = utils.checksums(in_file, ("md5", "sha256"))
        return {"size": size, "md5": md5, "sha256": sha256}

    @staticmethod
    def list_contents(fn, verbose=False, **kw):
        if not os.path.isabs(fn):
            fn = os.path.abspath(fn)
        streaming._list(str(fn), components=["pkg"], verbose=verbose)
