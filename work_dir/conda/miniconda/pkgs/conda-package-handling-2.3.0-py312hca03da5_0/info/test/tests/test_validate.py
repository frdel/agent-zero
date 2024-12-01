from pathlib import Path

from conda_package_handling.validate import validate_converted_files_match_streaming

from .test_api import data_dir, test_package_name, test_package_name_2


def test_validate_streaming():
    assert validate_converted_files_match_streaming(
        Path(data_dir, test_package_name + ".conda"),
        Path(data_dir, test_package_name + ".tar.bz2"),
        strict=False,
    ) == (Path(data_dir, test_package_name + ".conda"), [], [])

    # old converted files don't match uname, gname, mtime
    assert validate_converted_files_match_streaming(
        Path(data_dir, test_package_name + ".conda"),
        Path(data_dir, test_package_name + ".tar.bz2"),
        strict=True,
    ) != (Path(data_dir, test_package_name + ".conda"), [], [])

    src, missing, mismatched = validate_converted_files_match_streaming(
        Path(data_dir, test_package_name_2 + ".tar.bz2"),
        Path(data_dir, test_package_name + ".conda"),
        strict=False,
    )

    assert src == Path(data_dir, test_package_name_2 + ".tar.bz2")
    # not that critical exactly what mismatches; we are comparing separate packages
    assert len(missing) == 47
    assert mismatched == [
        "info/hash_input.json",
        "info/files",
        "info/index.json",
        "info/paths.json",
        "info/about.json",
        "info/git",
        "info/recipe/meta.yaml",
        "info/recipe/conda_build_config.yaml",
        "info/recipe/meta.yaml.template",
        "info/hash_input.json",
        "info/index.json",
        "info/files",
        "info/about.json",
        "info/paths.json",
        "info/git",
        "info/recipe/meta.yaml.template",
        "info/recipe/conda_build_config.yaml",
        "info/recipe/meta.yaml",
    ]
