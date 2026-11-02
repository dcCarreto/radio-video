from pathlib import Path

from radio_video.utils.paths import unique_output_path


def test_unused_name_is_kept(tmp_path: Path) -> None:
    assert unique_output_path(tmp_path, "movie", ".mp4") == tmp_path / "movie.mp4"


def test_existing_files_get_a_counter(tmp_path: Path) -> None:
    (tmp_path / "movie.mp4").touch()
    (tmp_path / "movie (1).mp4").touch()
    assert unique_output_path(tmp_path, "movie", ".mp4") == tmp_path / "movie (2).mp4"


def test_source_file_is_never_overwritten(tmp_path: Path) -> None:
    source = tmp_path / "song.mp3"
    source.touch()
    assert unique_output_path(tmp_path, source.stem, source.suffix) != source
