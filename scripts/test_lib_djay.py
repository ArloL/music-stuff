import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from lib_djay import (
    _extract_persistent_ids,
    _clone_db,
    load_djay_index,
    DJAY_KEY_INDEX_TO_OPEN_KEY,
)


# --- DJAY_KEY_INDEX_TO_OPEN_KEY ---

def test_key_map_is_bijection_over_all_open_keys():
    """Map covers indices 0-23 and produces exactly the 24 open keys (1d-12m)."""
    assert set(DJAY_KEY_INDEX_TO_OPEN_KEY.keys()) == set(range(24))
    expected = {f"{n}{s}" for n in range(1, 13) for s in ("d", "m")}
    assert set(DJAY_KEY_INDEX_TO_OPEN_KEY.values()) == expected


# --- _extract_persistent_ids ---

def test_extract_persistent_ids_both_prefixes():
    blob = (
        b'junk\x08com.apple.iTunes:111\x00'
        b'more\x08com.apple.Music:222\x00'
    )
    assert _extract_persistent_ids(blob) == [111, 222]


def test_extract_persistent_ids_negative_id():
    blob = b'\x08com.apple.iTunes:-5639804195476274594\x00'
    assert _extract_persistent_ids(blob) == [-5639804195476274594]


def test_extract_persistent_ids_wraps_large_unsigned_to_signed():
    """Values >= 2^63 are treated as unsigned and converted to signed."""
    large_val = (1 << 63) + 100
    blob = f'\x08com.apple.iTunes:{large_val}\x00'.encode()
    result = _extract_persistent_ids(blob)
    assert result == [large_val - (1 << 64)]
    assert result[0] < 0


def test_extract_persistent_ids_no_match():
    assert _extract_persistent_ids(b'') == []
    assert _extract_persistent_ids(b'no apple ids here') == []


# --- _clone_db ---

@patch("lib_djay.clonefile")
def test_clone_db_raises_if_source_missing(mock_clonefile, tmp_path):
    with patch("lib_djay.SOURCE_DB", tmp_path / "nonexistent.db"):
        with pytest.raises(FileNotFoundError, match="djay database not found"):
            _clone_db()
    mock_clonefile.assert_not_called()


@patch("lib_djay.clonefile")
def test_clone_db_clones_main_and_wal_shm(mock_clonefile, tmp_path):
    source = tmp_path / "MediaLibrary.db"
    source.touch()
    Path(str(source) + "-wal").touch()
    Path(str(source) + "-shm").touch()

    with patch("lib_djay.SOURCE_DB", source), patch("lib_djay.DB_PATH", tmp_path / "clone.db"):
        _clone_db()

    assert mock_clonefile.call_count == 3


@patch("lib_djay.clonefile")
def test_clone_db_skips_missing_wal_shm(mock_clonefile, tmp_path):
    source = tmp_path / "MediaLibrary.db"
    source.touch()

    with patch("lib_djay.SOURCE_DB", source), patch("lib_djay.DB_PATH", tmp_path / "clone.db"):
        _clone_db()

    mock_clonefile.assert_called_once()


# --- load_djay_index ---

def _make_test_db(db_path, rows):
    """Create a minimal sqlite DB mimicking djay's schema for testing."""
    con = sqlite3.connect(str(db_path))
    con.execute("""
        CREATE TABLE secondaryIndex_mediaItemAnalyzedDataIndex (
            rowid INTEGER PRIMARY KEY, bpm REAL, manualBPM REAL, keySignatureIndex INTEGER
        )
    """)
    con.execute("""
        CREATE TABLE database2 (
            rowid INTEGER PRIMARY KEY, key TEXT, collection TEXT, data BLOB
        )
    """)
    loc_rowid = 1000  # offset to avoid clash with analyzed rowids
    for i, (bpm, manual_bpm, key_idx, apple_id) in enumerate(rows, 1):
        con.execute(
            "INSERT INTO secondaryIndex_mediaItemAnalyzedDataIndex VALUES (?, ?, ?, ?)",
            (i, bpm, manual_bpm, key_idx),
        )
        key = f"track_{i}"
        con.execute(
            "INSERT INTO database2 (rowid, key, collection, data) VALUES (?, ?, 'mediaItemAnalyzedData', ?)",
            (i, key, b""),
        )
        blob = f'\x08com.apple.Music:{apple_id}\x00'.encode()
        con.execute(
            "INSERT INTO database2 (rowid, key, collection, data) VALUES (?, ?, 'localMediaItemLocations', ?)",
            (loc_rowid + i, key, blob),
        )
    con.commit()
    con.close()


@patch("lib_djay._clone_db")
def test_load_djay_index_maps_key_and_bpm(mock_clone, tmp_path):
    db = tmp_path / "test.db"
    _make_test_db(db, [
        (120.5, 121.0, 0, 12345),   # key index 0 -> "1d"
        (130.0, None, 5, 67890),     # key index 5 -> "3m", no manual BPM
    ])

    with patch("lib_djay.DB_PATH", db):
        result = load_djay_index()

    assert result[12345] == {"bpm": 120.5, "manual_bpm": 121.0, "open_key": "Key 1d"}
    assert result[67890] == {"bpm": 130.0, "manual_bpm": "", "open_key": "Key 3m"}


@patch("lib_djay._clone_db")
def test_load_djay_index_unknown_key_produces_empty_string(mock_clone, tmp_path):
    db = tmp_path / "test.db"
    _make_test_db(db, [(100.0, None, 99, 111)])

    with patch("lib_djay.DB_PATH", db):
        result = load_djay_index()

    assert result[111]["open_key"] == ""


@patch("lib_djay._clone_db")
def test_load_djay_index_deduplicates_by_pid(mock_clone, tmp_path):
    """If the same persistent ID appears in multiple rows, keep the first."""
    db = tmp_path / "test.db"
    con = sqlite3.connect(str(db))
    con.execute("""
        CREATE TABLE secondaryIndex_mediaItemAnalyzedDataIndex (
            rowid INTEGER PRIMARY KEY, bpm REAL, manualBPM REAL, keySignatureIndex INTEGER
        )
    """)
    con.execute("""
        CREATE TABLE database2 (
            rowid INTEGER PRIMARY KEY, key TEXT, collection TEXT, data BLOB
        )
    """)
    blob = b'\x08com.apple.Music:999\x00'
    for i, bpm in enumerate([120.0, 130.0], 1):
        key = f"track_{i}"
        con.execute("INSERT INTO secondaryIndex_mediaItemAnalyzedDataIndex VALUES (?, ?, ?, ?)", (i, bpm, None, 0))
        con.execute("INSERT INTO database2 VALUES (?, ?, 'mediaItemAnalyzedData', ?)", (i, key, b""))
        con.execute("INSERT INTO database2 VALUES (?, ?, 'localMediaItemLocations', ?)", (1000 + i, key, blob))
    con.commit()
    con.close()

    with patch("lib_djay.DB_PATH", db):
        result = load_djay_index()

    assert len(result) == 1
    assert result[999]["bpm"] == 120.0  # first row wins
