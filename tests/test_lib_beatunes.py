from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess

import pytest

FAKE_DB_PATH = Path("/tmp/beaTunes-FAKE.h2.db")

from music_stuff.lib.lib_beatunes import (
    hex_id_to_beatunes_id,
    beatunes_id_to_hex_id,
    lookup_songs,
    lookup_song,
    BeaTunesSong,
    SOURCE_DB_DIR,
    _parse_h2_list_output,
)


def test_hex_id_to_beatunes_id_high_bit_set():
    # "Never Said Goodbye" - hex has high bit set (B...)
    assert hex_id_to_beatunes_id("B1BB63F715E1025E") == 3583567841378501214


def test_hex_id_to_beatunes_id_high_bit_unset():
    # hex with high bit unset (0...) should produce negative beaTunes ID
    assert hex_id_to_beatunes_id("0575419A2E6CA0A4") < 0


def test_beatunes_id_to_hex_id_positive():
    assert beatunes_id_to_hex_id(3583567841378501214) == "B1BB63F715E1025E"


def test_beatunes_id_to_hex_id_negative():
    assert beatunes_id_to_hex_id(-8830079363930349404) == "0575419A2E6CA0A4"


def test_round_trip_from_hex():
    hex_id = "B1BB63F715E1025E"
    assert beatunes_id_to_hex_id(hex_id_to_beatunes_id(hex_id)) == hex_id


def test_round_trip_from_beatunes_id():
    beatunes_id = 3583567841378501214
    assert hex_id_to_beatunes_id(beatunes_id_to_hex_id(beatunes_id)) == beatunes_id


def test_hex_id_padded_to_16_chars():
    # Small beaTunes ID should still produce a zero-padded 16-char hex string
    result = beatunes_id_to_hex_id(0)
    assert len(result) == 16
    assert result == "8000000000000000"


# --- H2 list-mode output parsing tests ---

PREAMBLE = (
    "Welcome to H2 Shell 1.4.195 (2017-04-23)\n"
    "Exit with Ctrl+C\n"
    "Commands are case insensitive; SQL statements end with ';'\n"
    "help or ?      Display this help\n"
    "list           Toggle result list / stack trace mode\n"
    "maxwidth       Set maximum column width (default is 100)\n"
    "autocommit     Enable or disable autocommit\n"
    "history        Show the last 20 statements\n"
    "quit or exit   Close the connection and exit\n"
    "\n"
    "sql> Result list mode is now on\n"
)


def test_parse_h2_list_output_single_row():
    output = (
        PREAMBLE
        + "sql> ID      : 3583567841378501214\n"
        "EXACTBPM: 115.02\n"
        "TONALKEY: 24\n"
        "ARTIST  : Dorothy's Ghost\n"
        "NAME    : Never Said Goodbye\n"
        "(1 row, 12 ms)\n"
    )
    rows = _parse_h2_list_output(output)
    assert len(rows) == 1
    assert rows[0]["ID"] == "3583567841378501214"
    assert rows[0]["EXACTBPM"] == "115.02"
    assert rows[0]["TONALKEY"] == "24"
    assert rows[0]["ARTIST"] == "Dorothy's Ghost"
    assert rows[0]["NAME"] == "Never Said Goodbye"


def test_parse_h2_list_output_multiple_rows():
    output = (
        PREAMBLE
        + "sql> ID      : 111\n"
        "EXACTBPM: 120.0\n"
        "TONALKEY: 1\n"
        "ARTIST  : Artist A\n"
        "NAME    : Song A\n"
        "\n"
        "ID      : 222\n"
        "EXACTBPM: 130.0\n"
        "TONALKEY: 2\n"
        "ARTIST  : Artist B\n"
        "NAME    : Song B\n"
        "(2 rows, 5 ms)\n"
    )
    rows = _parse_h2_list_output(output)
    assert len(rows) == 2
    assert rows[0]["ID"] == "111"
    assert rows[1]["ID"] == "222"


def test_parse_h2_list_output_empty():
    rows = _parse_h2_list_output("")
    assert rows == []


def test_parse_h2_list_output_no_data_rows():
    output = PREAMBLE + "sql> (0 rows, 3 ms)\n"
    rows = _parse_h2_list_output(output)
    assert rows == []


# --- lookup tests with mocked subprocess ---

H2_OUTPUT = (
    PREAMBLE
    + "sql> ID      : 3583567841378501214\n"
    "EXACTBPM: 115.02\n"
    "TONALKEY: 24\n"
    "ARTIST  : Dorothy's Ghost\n"
    "NAME    : Never Said Goodbye\n"
    "(1 row, 12 ms)\n"
)


@patch("music_stuff.lib.lib_beatunes._clone_db", return_value=FAKE_DB_PATH)
@patch("subprocess.run")
def test_lookup_songs(mock_run, mock_clone):
    mock_run.return_value = MagicMock(stdout=H2_OUTPUT)
    result = lookup_songs(["B1BB63F715E1025E"])
    assert "B1BB63F715E1025E" in result
    song = result["B1BB63F715E1025E"]
    assert isinstance(song, BeaTunesSong)
    assert song.exactbpm == 115.02
    assert song.key == "Key 12m"
    assert song.artist == "Dorothy's Ghost"
    assert song.name == "Never Said Goodbye"


@patch("music_stuff.lib.lib_beatunes._clone_db", return_value=FAKE_DB_PATH)
@patch("subprocess.run")
def test_lookup_song(mock_run, mock_clone):
    mock_run.return_value = MagicMock(stdout=H2_OUTPUT)
    song = lookup_song("B1BB63F715E1025E")
    assert song is not None
    assert song.exactbpm == 115.02
    assert song.key == "Key 12m"


@patch("music_stuff.lib.lib_beatunes._clone_db", return_value=FAKE_DB_PATH)
@patch("subprocess.run")
def test_lookup_song_not_found(mock_run, mock_clone):
    mock_run.return_value = MagicMock(
        stdout=PREAMBLE + "sql> (0 rows, 3 ms)\n"
    )
    song = lookup_song("0000000000000001")
    assert song is None


def test_lookup_songs_empty():
    result = lookup_songs([])
    assert result == {}


@patch("music_stuff.lib.lib_beatunes._clone_db", return_value=FAKE_DB_PATH)
@patch("subprocess.run")
def test_lookup_songs_null_fields(mock_run, mock_clone):
    output = (
        PREAMBLE
        + "sql> ID      : 3583567841378501214\n"
        "EXACTBPM: null\n"
        "TONALKEY: null\n"
        "ARTIST  : Dorothy's Ghost\n"
        "NAME    : Never Said Goodbye\n"
        "(1 row, 5 ms)\n"
    )
    mock_run.return_value = MagicMock(stdout=output)
    result = lookup_songs(["B1BB63F715E1025E"])
    song = result["B1BB63F715E1025E"]
    assert song.exactbpm is None
    assert song.key == ""


# --- Integration test (skipped if DB not present) ---

@pytest.mark.skipif(
    not any(SOURCE_DB_DIR.glob("beaTunes-*.h2.db")),
    reason="beaTunes database not available",
)
def test_integration_never_said_goodbye():
    song = lookup_song("B1BB63F715E1025E")
    assert song is not None
    assert 114 <= song.exactbpm <= 116
    assert song.key == "Key 12m"
    assert "Never Said Goodbye" in song.name
