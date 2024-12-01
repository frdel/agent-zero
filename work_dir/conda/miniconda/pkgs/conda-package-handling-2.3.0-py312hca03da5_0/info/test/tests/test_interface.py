"""
Test format classes.

(Some of their code is unreachable through api.py)
"""

import os
from pathlib import Path

import pytest

from conda_package_handling.conda_fmt import CondaFormat_v2
from conda_package_handling.tarball import CondaTarBZ2

from .test_api import data_dir, test_package_name

TEST_CONDA = Path(data_dir, test_package_name + ".conda")
TEST_TARBZ = Path(data_dir, test_package_name + ".tar.bz2")


def test_extract_create(tmpdir):
    for format, infile, outfile in (
        (CondaFormat_v2, TEST_CONDA, "newmock.conda"),
        (CondaTarBZ2, TEST_TARBZ, "newmock.tar.bz2"),
    ):
        both_path = Path(tmpdir, f"mkdirs-{outfile.split('.', 1)[-1]}")

        # these old APIs don't guarantee Path-like's
        format.extract(infile, str(both_path))
        assert sorted(os.listdir(both_path)) == sorted(["lib", "info"])

        if format == CondaFormat_v2:
            info_path = Path(tmpdir, "info-only")
            format.extract_info(TEST_CONDA, str(info_path))  # type: ignore
            assert os.listdir(info_path) == ["info"]

        filelist = [str(p.relative_to(both_path)) for p in both_path.rglob("*")]
        format.create(
            both_path,
            filelist,
            tmpdir / outfile,
            # compression_tuple is for libarchive compatibility. Instead, pass
            # compressor=(compressor factory function)
            compression_tuple=(".tar.zst", "zstd", "zstd:compression-level=1"),
        )

        assert (tmpdir / outfile).exists()

        with pytest.raises(ValueError):
            CondaFormat_v2.create(
                "", [], "", compressor=True, compression_tuple=("1", "2", "3")  # type: ignore
            )
