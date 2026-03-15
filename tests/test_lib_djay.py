import sqlite3
import struct
from pathlib import Path
from unittest.mock import patch

import pytest

from music_stuff.lib.lib_djay import (
    _extract_persistent_ids,
    _extract_automix_data,
    _clone_db,
    load_djay_index,
    DjaySongData,
    DJAY_KEY_INDEX_TO_OPEN_KEY,
    parse_tsaf,
    TsafEntity,
)


# --- DJAY_KEY_INDEX_TO_OPEN_KEY ---


def test_key_map_is_bijection_over_all_open_keys():
    """Map covers indices 0-23 and produces exactly the 24 open keys (1d-12m)."""
    assert set(DJAY_KEY_INDEX_TO_OPEN_KEY.keys()) == set(range(24))
    expected = {f"{n}{s}" for n in range(1, 13) for s in ("d", "m")}
    assert set(DJAY_KEY_INDEX_TO_OPEN_KEY.values()) == expected


# --- _extract_persistent_ids ---


def test_extract_persistent_ids_negative_id():
    blob = b"\x08com.apple.iTunes:-5639804195476274594\x00"
    assert _extract_persistent_ids(blob) == ["B1BB63F715E1025E"]


def test_extract_persistent_ids_wraps_large_unsigned_to_signed():
    """Values >= 2^63 are stored as hex strings."""
    large_val = (1 << 63) + 100
    blob = f"\x08com.apple.iTunes:{large_val}\x00".encode()
    result = _extract_persistent_ids(blob)
    assert result == [format(large_val, "016X")]


def test_extract_persistent_ids_no_match():
    assert _extract_persistent_ids(b"") == []
    assert _extract_persistent_ids(b"no apple ids here") == []


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


# --- _extract_automix_data ---

# First 420 bytes of real mediaItemUserData blobs from known tracks.
# Verified: cue_start_time ≈ 14.994s, cue_end_time ≈ 252.996s
_BLOB_87DE = bytes.fromhex(
    "54534146030003000900000000000000180000002b084144434d656469614974656d557365724461746100"
    "083932633836366565363339653239626365353336313165623131313432623032000875756964000b060000"
    "00086175746f6d69785374617274506f696e740008656e64506f696e740008617564696f416c69676e6d656e"
    "7446696e6765727072696e7400087469746c6549447300086175746f6d6978456e64506f696e740008706c61"
    "79436f756e740008757365724368616e676564436c6f75644b657973000b000000010000002b084144434d65"
    "6469614974656d5469746c6549440005010502084772696e6400087469746c6500084c65732053696e730008"
    "61727469737400130073089f43086475726174696f6e000005062b08414443437565506f696e740013fdfe7c"
    "430874696d65001300000080bf08656e6454696d65002e086e756d626572000005042b0510130000003ff56f"
    "4105111300000080bf05122e05130005032b051013fdfe7c4305111300000080bf05122e05130005072b0841"
    "4443417564696f416c69676e6d656e7446696e676572707269"
)
# Verified: cue_start_time ≈ 23.386s, cue_end_time ≈ 481.788s
_BLOB_4D24 = bytes.fromhex(
    "54534146030003000900000000000000180000002b084144434d656469614974656d557365724461746100"
    "083363303035366233623830346136363662386166306637326233396239663238000875756964000b060000"
    "00086175746f6d69785374617274506f696e740008656e64506f696e740008617564696f416c69676e6d656e"
    "7446696e6765727072696e7400087469746c6549447300086175746f6d6978456e64506f696e740008706c61"
    "79436f756e740008757365724368616e676564436c6f75644b657973000b000000010000002b084144434d65"
    "6469614974656d5469746c654944000501050208416567697300087469746c650008416e6472652042726174"
    "74656e000861727469737400131b070644086475726174696f6e000005062b08414443437565506f696e7400"
    "13d5e4f0430874696d65001300000080bf08656e6454696d65002e086e756d626572000005042b0510130000"
    "008c15bb4105111300000080bf05122e05130005032b051013d5e4f04305111300000080bf05122e05130005"
    "072b08414443417564696f416c69676e6d656e7446696e6765"
)


def _make_dmiud_data(*, cue_start_time=None, cue_time=None):
    """Build a minimal TSAF-style mediaItemUserData blob for testing."""
    header = b"TSAF\x03\x00\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    parts = [header]

    if cue_time is not None or cue_start_time is not None:
        entity = b"\x2b\x08ADCCuePoint\x00"
        if cue_time is not None:
            entity += b"\x13" + struct.pack("<f", cue_time) + b"\x08time\x00"
        entity += b"\x13" + struct.pack("<f", -1.0) + b"\x08endTime\x00"
        entity += b"\x0f" + struct.pack("<B", 0) + b"\x08number\x00"
        parts.append(entity)

    if cue_start_time is not None:
        entity = (
            b"\x2b\x05\x10\x13\x00\x00\x00"
            + struct.pack("<f", cue_start_time)
            + b"\x05\x11"
        )
        parts.append(entity)

    return b"".join(parts)


def test_extract_automix_data_all_fields():
    blob = _make_dmiud_data(cue_start_time=10.0, cue_time=200.5)
    cs, ct = _extract_automix_data(blob)
    assert abs(cs - 10.0) < 0.01
    assert abs(ct - 200.5) < 0.01


def test_extract_automix_data_start_only():
    blob = _make_dmiud_data()
    cs, ct = _extract_automix_data(blob)
    assert cs is None
    assert ct is None


def test_extract_automix_data_cue_only():
    blob = _make_dmiud_data(cue_time=150.0)
    cs, ct = _extract_automix_data(blob)
    assert cs is None
    assert abs(ct - 150.0) < 0.01


def test_extract_automix_data_empty():
    assert _extract_automix_data(b"nothing here") == (None, None)


def test_extract_automix_data_real_blob_87de():
    """Real blob from track 87DE3E4D500A6326: start ≈ 14.9s, end ≈ 252.9s."""
    cs, ct = _extract_automix_data(_BLOB_87DE)
    assert cs is not None
    assert abs(cs - 14.994) < 0.01
    assert ct is not None
    assert abs(ct - 252.996) < 0.01


def test_extract_automix_data_real_blob_4d24():
    """Real blob from track 4D24CEA1A632921F: start ≈ 23.4s, end ≈ 481.8s."""
    cs, ct = _extract_automix_data(_BLOB_4D24)
    assert abs(cs - 23.386) < 0.01
    assert ct is not None
    assert abs(ct - 481.788) < 0.01


# --- load_djay_index ---


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
    for i, (bpm, manual_bpm, key_index, apple_music_id, dmiud_data) in enumerate(rows, 1):
        con.execute(
            "INSERT INTO secondaryIndex_mediaItemAnalyzedDataIndex VALUES (?, ?, ?, ?)",
            (i, bpm, None, key_index),
        )
        key = f"song_{i}"
        con.execute(
            "INSERT INTO database2 (rowid, key, collection, data) VALUES (?, ?, 'mediaItemAnalyzedData', ?)",
            (i, key, b""),
        )
        blob = f"\x08com.apple.iTunes:{apple_music_id}\x00".encode()
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
def test_load_djay_index_includes_automix_data(mock_clone, tmp_path):
    db = tmp_path / "test.db"
    ud = _make_dmiud_data(cue_time=200.5)
    _make_test_db(db, [(120.0, None, 0, 12345, ud)])

    with patch("music_stuff.lib.lib_djay.DB_PATH", db):
        result = load_djay_index()

    entry = result["0000000000003039"]
    assert abs(entry.cue_end_time - 200.5) < 0.01


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


# --- parse_tsaf ---


def test_parse_tsaf_entity_types():
    entities = parse_tsaf(_BLOB_87DE)
    type_names = [e.type_name for e in entities]
    assert "ADCMediaItemUserData" in type_names
    assert "ADCMediaItemTitleID" in type_names
    assert "ADCCuePoint" in type_names


def test_parse_tsaf_root_fields():
    entities = parse_tsaf(_BLOB_87DE)
    for e in entities:
        if e.type_name == "ADCMediaItemUserData":
            assert e.fields.get("automixStartPoint") == 6
            break
    else:
        pytest.fail("ADCMediaItemUserData not found")


def test_parse_tsaf_title_id():
    entities = parse_tsaf(_BLOB_87DE)
    for e in entities:
        if e.type_name == "ADCMediaItemTitleID":
            assert len(e.fields) > 0
            break
    else:
        pytest.fail("ADCMediaItemTitleID not found")


def test_parse_tsaf_verbose_cue_point():
    entities = parse_tsaf(_BLOB_87DE)
    for e in entities:
        if e.type_name == "ADCCuePoint" and not e.compact:
            time_val = e.fields.get("time")
            assert time_val is not None
            assert abs(time_val - 252.996) < 0.01
            end_time = e.fields.get("endTime")
            assert end_time is not None
            assert abs(end_time - (-1.0)) < 0.01
            number = e.fields.get("number")
            assert number == 46
            break
    else:
        pytest.fail("Verbose ADCCuePoint not found")


def test_parse_tsaf_compact_cue_point():
    entities = parse_tsaf(_BLOB_87DE)
    compact_cues = [e for e in entities if e.type_name == "ADCCuePoint" and e.compact]
    assert len(compact_cues) >= 1
    cue = compact_cues[0]
    time_val = cue.fields.get("time")
    assert time_val is not None
    assert abs(time_val - 14.994) < 0.01
    number = cue.fields.get("number")
    assert number == 46


def test_parse_tsaf_compact_field_names():
    entities = parse_tsaf(_BLOB_87DE)
    for e in entities:
        if e.type_name == "ADCCuePoint" and e.compact:
            assert "time" in e.fields
            assert "endTime" in e.fields
            assert "number" in e.fields
            break
    else:
        pytest.fail("Compact ADCCuePoint not found")


def test_parse_tsaf_empty():
    assert parse_tsaf(b"") == []
    assert parse_tsaf(b"not a blob") == []


def test_parse_tsaf_escape_byte():
    blob = (
        b"TSAF\x03\x00\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x2b\x08TestEntity\x00"
        b"\x13\x08\x00\x00\x00"
        b"\x08testField\x00"
    )
    entities = parse_tsaf(blob)
    assert len(entities) == 1
    assert entities[0].type_name == "TestEntity"
    assert "testField" in entities[0].fields
