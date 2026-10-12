from pathlib import Path
import zipfile

from helpers.file_browser import prepare_files_download


def test_single_folder_download_is_named_after_the_folder(tmp_path: Path) -> None:
    folder = tmp_path / "my-folder"
    folder.mkdir()
    (folder / "file.txt").write_text("content", encoding="utf-8")

    # A single selected folder downloads as <folder>.zip, not the generic
    # agent-zero-selected-<count>-<stamp>.zip archive name.
    download = prepare_files_download([str(folder)], current_path=str(tmp_path))
    try:
        assert download["download_name"] == "my-folder.zip"
        assert zipfile.is_zipfile(download["file_source"])
    finally:
        Path(download["file_source"]).unlink(missing_ok=True)


def test_multi_selection_download_keeps_generic_archive_name(tmp_path: Path) -> None:
    one = tmp_path / "one.txt"
    two = tmp_path / "two.txt"
    one.write_text("1", encoding="utf-8")
    two.write_text("2", encoding="utf-8")

    download = prepare_files_download([str(one), str(two)], current_path=str(tmp_path))
    try:
        # True multi-selections keep the timestamped generic archive name.
        assert download["download_name"].startswith("agent-zero-selected-2-")
        assert download["download_name"].endswith(".zip")
    finally:
        Path(download["file_source"]).unlink(missing_ok=True)
