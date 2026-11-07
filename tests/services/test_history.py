from __future__ import annotations

from datetime import datetime
from pathlib import Path

from radio_video.services.history import (
    HistoryRecord,
    HistoryResult,
    HistoryStore,
    output_missing,
)


def _record(
    tmp_path: Path, name: str = "clip", result: HistoryResult = HistoryResult.SAVED
) -> HistoryRecord:
    return HistoryRecord(
        when=datetime(2026, 11, 7, 14, 32),
        source=tmp_path / f"{name}.mkv",
        output=tmp_path / f"{name}.mp4" if result is HistoryResult.SAVED else None,
        format_key="mp4-h264",
        quality="Balanced",
        custom=False,
        result=result,
        size=1234 if result is HistoryResult.SAVED else None,
        took=43.2,
        fraction=0.18 if result is HistoryResult.CANCELED else 1.0,
        error="boom" if result is HistoryResult.FAILED else "",
    )


def test_records_survive_a_restart(tmp_path: Path) -> None:
    path = tmp_path / "data" / "history.json"
    store = HistoryStore(path)
    first = _record(tmp_path, "a")
    second = _record(tmp_path, "b", HistoryResult.FAILED)
    store.add(first)
    store.add(second)
    reloaded = HistoryStore(path)
    assert reloaded.records == (second, first)


def test_only_the_latest_are_kept(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history.json", limit=3)
    for number in range(5):
        store.add(_record(tmp_path, f"f{number}"))
    assert [r.source.stem for r in store.records] == ["f4", "f3", "f2"]
    assert len(HistoryStore(tmp_path / "history.json", limit=3).records) == 3


def test_clear(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history.json")
    store.add(_record(tmp_path))
    store.clear()
    assert HistoryStore(tmp_path / "history.json").records == ()


def test_damaged_file_is_set_aside(tmp_path: Path) -> None:
    path = tmp_path / "history.json"
    path.write_text("{not json", encoding="utf-8")
    store = HistoryStore(path)
    assert store.records == ()
    assert list(tmp_path.glob("history.damaged-*.json"))
    store.add(_record(tmp_path))
    assert len(HistoryStore(path).records) == 1


def test_output_missing(tmp_path: Path) -> None:
    saved = _record(tmp_path)
    assert output_missing(saved)
    assert saved.output is not None
    saved.output.write_bytes(b"x")
    assert not output_missing(saved)
    assert not output_missing(_record(tmp_path, result=HistoryResult.FAILED))
