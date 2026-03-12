import csv
from unittest.mock import patch

from music_stuff.lib.lib_apple_music import AppleMusicSong

import importlib
playlist_csv = importlib.import_module("music_stuff.playlist-csv")


def test_write_playlist_to_file(tmp_path):
    songs = [
        AppleMusicSong(
            persistentID="ABC123", name="Song A", artist="Artist 1",
            comment="Key 6d", bpm=120, location="", rating=80,
        ),
        AppleMusicSong(
            persistentID="DEF456", name="Song B", artist="Artist 2",
            comment="Key 3m", bpm=0, location="", rating=60,
        ),
    ]

    with patch.object(playlist_csv, "find_songs_by_playlist_name", return_value=songs), \
         patch.object(playlist_csv, "OUTPUT_DIR", tmp_path):
        playlist_csv.write_playlist_to_file("My Test Playlist")

    output = tmp_path / "songs-my-test-playlist.csv"
    assert output.exists()

    with open(output, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 2
    assert rows[0] == {
        "apple_music_id": "ABC123", "artist": "Artist 1", "name": "Song A",
        "key": "Key 6d", "bpm": "120",
    }
    assert rows[1] == {
        "apple_music_id": "DEF456", "artist": "Artist 2", "name": "Song B",
        "key": "Key 3m", "bpm": "",
    }
