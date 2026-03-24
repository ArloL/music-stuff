import sqlite3
import struct
from pathlib import Path
from unittest.mock import patch

import pytest

from music_stuff.lib.lib_djay import (
    DJAY_KEY_INDEX_TO_OPEN_KEY,
    DjaySongData,
    _clone_db,
    load_djay_index,
)

# --- DJAY_KEY_INDEX_TO_OPEN_KEY ---


def test_key_map_is_bijection_over_all_open_keys():
    """Map covers indices 0-23 and produces exactly the 24 open keys (1d-12m)."""
    assert set(DJAY_KEY_INDEX_TO_OPEN_KEY.keys()) == set(range(24))
    expected = {f"{n}{s}" for n in range(1, 13) for s in ("d", "m")}
    assert set(DJAY_KEY_INDEX_TO_OPEN_KEY.values()) == expected


# --- _clone_db ---


@patch("music_stuff.lib.lib_djay.clonefile")
def test_clone_db_raises_if_source_missing(mock_clonefile, tmp_path):
    with patch("music_stuff.lib.lib_djay.SOURCE_DB", tmp_path / "nonexistent.db"):
        with pytest.raises(FileNotFoundError, match="djay database not found"):
            _clone_db()
    mock_clonefile.assert_not_called()


@patch("music_stuff.lib.lib_djay.clonefile")
def test_clone_db_clones_main_and_wal_shm(mock_clonefile, tmp_path):
    source = tmp_path / "MediaLibrary.db"
    source.touch()
    Path(str(source) + "-wal").touch()
    Path(str(source) + "-shm").touch()

    with (
        patch("music_stuff.lib.lib_djay.SOURCE_DB", source),
        patch("music_stuff.lib.lib_djay.DB_PATH", tmp_path / "clone.db"),
    ):
        _clone_db()

    assert mock_clonefile.call_count == 3


@patch("music_stuff.lib.lib_djay.clonefile")
def test_clone_db_skips_missing_wal_shm(mock_clonefile, tmp_path):
    source = tmp_path / "MediaLibrary.db"
    source.touch()

    with (
        patch("music_stuff.lib.lib_djay.SOURCE_DB", source),
        patch("music_stuff.lib.lib_djay.DB_PATH", tmp_path / "clone.db"),
    ):
        _clone_db()

    mock_clonefile.assert_called_once()


# --- helpers for load_djay_index tests ---


def _make_dlmil_blob(apple_music_id: int) -> bytes:
    """Build a minimal valid TSAF localMediaItemLocations blob containing the given Apple Music ID."""
    data = bytearray()
    p = [0]

    def wb(b: int) -> None:
        data.append(b)
        p[0] += 1

    def wr(b: bytes) -> None:
        data.extend(b)
        p[0] += len(b)

    def wcstr(s: str) -> None:
        wr(s.encode() + b"\x00")

    def wnum(raw: bytes, align: int) -> None:
        if align > 1:
            pad = (align - p[0] % align) % align
            wr(b"\x00" * pad)
        wr(raw)

    # TSAF header (20 bytes)
    wr(b"TSAF\x03\x00\x03\x00\x01\x00\x00\x00\x00\x00\x00\x00\x18\x00\x00\x00")
    # Verbose entity E with one Apple ID collection
    wb(0x2B)
    wb(0x08)
    wcstr("E")
    # Anonymous Apple ID collection (name=None — next byte after items is not 0x08)
    wb(0x0B)
    wnum(struct.pack("<I", 1), 4)
    wb(0x21)
    wb(0x08)
    wcstr(f"com.apple.iTunes:{apple_music_id}")
    # End of entity
    wb(0x00)
    return bytes(data)


def _make_test_db(db_path, rows):
    """Create a minimal sqlite DB mimicking djay's schema for testing.

    rows: list of (bpm, manual_bpm, key_index, apple_music_id, dmiud_data)
    dmiud_data may be None to simulate a track with no mediaItemUserData row.
    """
    con = sqlite3.connect(str(db_path))
    con.execute("""
        CREATE TABLE "database2" (
            "rowid" INTEGER PRIMARY KEY, "key" TEXT, "collection" TEXT, "data" BLOB
        )
    """)
    con.execute("""
        CREATE TABLE "secondaryIndex_mediaItemAnalyzedDataIndex" (
            "rowid" INTEGER PRIMARY KEY, "bpm" REAL, "manualBPM" REAL, "keySignatureIndex" INTEGER
        )
    """)
    con.execute("""
        CREATE TABLE "secondaryIndex_mediaItemLocationIndex" (
            "rowid" INTEGER PRIMARY KEY, "fileName" TEXT
        )
    """)
    con.execute("""
        CREATE TABLE "secondaryIndex_mediaItemUserDataIndex" (
            "rowid" INTEGER PRIMARY KEY, "tags" TEXT, "manualBPM" REAL
        )
    """)
    dlmil_rowid_start = 1000
    dmiud_rowid_start = 2000
    for i, (bpm, manual_bpm, key_index, apple_music_id, dmiud_data) in enumerate(
        rows, 1
    ):
        con.execute(
            "INSERT INTO secondaryIndex_mediaItemAnalyzedDataIndex VALUES (?, ?, ?, ?)",
            (i, bpm, None, key_index),
        )
        key = f"song_{i}"
        con.execute(
            "INSERT INTO database2 (rowid, key, collection, data) VALUES (?, ?, 'mediaItemAnalyzedData', ?)",
            (i, key, b""),
        )
        blob = _make_dlmil_blob(apple_music_id)
        con.execute(
            "INSERT INTO database2 (rowid, key, collection, data) VALUES (?, ?, 'localMediaItemLocations', ?)",
            (dlmil_rowid_start + i, key, blob),
        )
        if dmiud_data is not None or manual_bpm is not None:
            if manual_bpm is not None:
                con.execute(
                    "INSERT INTO secondaryIndex_mediaItemUserDataIndex VALUES (?, ?, ?)",
                    (dmiud_rowid_start + i, None, manual_bpm),
                )
            con.execute(
                "INSERT INTO database2 (rowid, key, collection, data) VALUES (?, ?, 'mediaItemUserData', ?)",
                (dmiud_rowid_start + i, key, dmiud_data),
            )
    con.commit()
    con.close()


# --- load_djay_index ---


@patch("music_stuff.lib.lib_djay._clone_db")
def test_load_djay_index_maps_key_and_bpm(mock_clone, tmp_path):
    db = tmp_path / "test.db"
    _make_test_db(
        db,
        [
            (120.5, 121.0, 0, 12345, None),  # key index 0 -> "1d"
            (130.0, None, 5, 67890, None),  # key index 5 -> "3m", no manual BPM
        ],
    )

    with patch("music_stuff.lib.lib_djay.DB_PATH", db):
        result = load_djay_index()

    assert result["0000000000003039"] == DjaySongData(
        id="song_1",
        bpm=120.5,
        manual_bpm=121.0,
        key="1d",
        is_straight_grid=False,
        cue_start_time=None,
        cue_end_time=None,
    )
    assert result["0000000000010932"] == DjaySongData(
        id="song_2",
        bpm=130.0,
        manual_bpm="",
        key="3m",
        is_straight_grid=False,
        cue_start_time=None,
        cue_end_time=None,
    )


@patch("music_stuff.lib.lib_djay._clone_db")
def test_load_djay_index_automix_none_when_no_userdata(mock_clone, tmp_path):
    db = tmp_path / "test.db"
    _make_test_db(db, [(120.0, None, 0, 99, None)])

    with patch("music_stuff.lib.lib_djay.DB_PATH", db):
        result = load_djay_index()

    entry = result["0000000000000063"]
    assert entry.cue_start_time is None


@patch("music_stuff.lib.lib_djay._clone_db")
def test_load_djay_index_unknown_key_produces_empty_string(mock_clone, tmp_path):
    db = tmp_path / "test.db"
    _make_test_db(db, [(100.0, None, 99, 111, None)])

    with patch("music_stuff.lib.lib_djay.DB_PATH", db):
        result = load_djay_index()

    assert result["000000000000006F"].key == ""
