import json
import shutil
import subprocess
import uuid
from unittest.mock import MagicMock, patch

import pytest

from music_stuff.lib.lib_apple_music import (
    AppleMusicSong,
    _to_song,
    create_playlist,
    delete_playlist,
    find_playlist_by_name,
    find_song_by_id,
    find_songs_by_folder_name,
    find_songs_by_playlist_name,
    set_song_bpm,
    set_song_key,
)


def _try_launch_music() -> bool:
    """Try to launch Music.app and verify the library is accessible via JXA."""
    if shutil.which("osascript") is None:
        return False
    try:
        subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", 'Application("Music").launch()'],
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Probe that the library is actually queryable, not just that the app launched
        result = subprocess.run(
            [
                "osascript",
                "-l",
                "JavaScript",
                "-e",
                'Application("Music").playlists.length',
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


needs_osascript = pytest.mark.skipif(
    not _try_launch_music(),
    reason="Music app unavailable",
)


# --- _to_song ---


def test_to_song_extracts_key_from_comment():
    raw = {
        "persistentID": "ABC",
        "name": "T",
        "artist": "A",
        "comment": "Key 6d",
        "bpm": 120,
        "location": "",
    }
    song = _to_song(raw)
    assert song.key == "6d"


def test_to_song_extracts_minor_key():
    raw = {
        "persistentID": "ABC",
        "name": "T",
        "artist": "A",
        "comment": "Key 3M",
        "bpm": 120,
        "location": "",
    }
    song = _to_song(raw)
    assert song.key == "3m"


def test_to_song_key_embedded_in_comment():
    raw = {
        "persistentID": "ABC",
        "name": "T",
        "artist": "A",
        "comment": "some text Key 11d more text",
        "bpm": 120,
        "location": "",
    }
    song = _to_song(raw)
    assert song.key == "11d"


def test_to_song_empty_key_when_no_comment():
    raw = {
        "persistentID": "ABC",
        "name": "T",
        "artist": "A",
        "comment": "",
        "bpm": 120,
        "location": "",
    }
    song = _to_song(raw)
    assert song.key == ""


def test_to_song_empty_key_when_comment_has_no_key():
    raw = {
        "persistentID": "ABC",
        "name": "T",
        "artist": "A",
        "comment": "ignore",
        "bpm": 120,
        "location": "",
    }
    song = _to_song(raw)
    assert song.key == ""


def test_to_song_missing_optional_fields():
    raw = {"persistentID": "ABC"}
    song = _to_song(raw)
    assert song.id == "ABC"
    assert song.name == ""
    assert song.artist == ""
    assert song.bpm == 0
    assert song.rating == 0
    assert song.genre == ""
    assert song.key == ""


def test_to_song_maps_all_fields():
    raw = {
        "persistentID": "DEADBEEF",
        "name": "My Song",
        "artist": "DJ Test",
        "comment": "Key 9m",
        "bpm": 138,
        "location": "/path/to/file.mp3",
        "rating": 100,
        "genre": "Techno",
    }
    song = _to_song(raw)
    assert song.id == "DEADBEEF"
    assert song.name == "My Song"
    assert song.artist == "DJ Test"
    assert song.comment == "Key 9m"
    assert song.bpm == 138
    assert song.location == "/path/to/file.mp3"
    assert song.rating == 100
    assert song.genre == "Techno"
    assert song.key == "9m"


# --- create_playlist ---


def test_create_playlist_passes_name_and_ids_to_jxa():
    mock = MagicMock(
        returncode=0,
        stdout=json.dumps({"name": "My Set", "persistentID": "P1", "trackCount": 2}),
    )
    with patch(
        "music_stuff.lib.lib_apple_music.subprocess.run", return_value=mock
    ) as mock_run:
        result = create_playlist("My Set", ["AAA", "BBB"])
    script = mock_run.call_args.kwargs["input"]
    assert json.dumps("My Set") in script
    assert json.dumps(["AAA", "BBB"]) in script
    assert result["trackCount"] == 2


def test_create_playlist_raises_on_error():
    mock = MagicMock(
        returncode=1, stderr="execution error: Error: Track not found: ZZZ (-2700)"
    )
    with patch("music_stuff.lib.lib_apple_music.subprocess.run", return_value=mock):
        with pytest.raises(RuntimeError, match="Track not found"):
            create_playlist("My Set", ["ZZZ"])


def test_delete_playlist_passes_id_to_jxa():
    mock = MagicMock(returncode=0, stdout="null")
    with patch(
        "music_stuff.lib.lib_apple_music.subprocess.run", return_value=mock
    ) as mock_run:
        delete_playlist("P1")
    script = mock_run.call_args.kwargs["input"]
    assert json.dumps("P1") in script


def test_delete_playlist_raises_on_error():
    mock = MagicMock(
        returncode=1, stderr="execution error: Error: Playlist not found: P1 (-2700)"
    )
    with patch("music_stuff.lib.lib_apple_music.subprocess.run", return_value=mock):
        with pytest.raises(RuntimeError, match="Playlist not found"):
            delete_playlist("P1")


@needs_osascript
def test_create_playlist_creates_populates_and_deletes():
    """End-to-end: build a real playlist, verify its tracks (in order), then
    delete it. Uses a unique name so it never collides with the live library."""
    songs = find_songs_by_folder_name("Test Folder")
    assert len(songs) >= 2, "Test Folder needs at least two tracks"
    track_ids = [songs[0].id, songs[1].id]
    name = f"music-stuff test {uuid.uuid4().hex[:8]}"

    result = create_playlist(name, track_ids)
    try:
        assert result["name"] == name
        assert result["trackCount"] == 2
        assert result["persistentID"]
        # Tracks land in the playlist in the order they were added.
        added = find_songs_by_playlist_name(name)
        assert [s.id for s in added] == track_ids
    finally:
        delete_playlist(result["persistentID"])

    # The playlist is gone (find_playlist_by_name raises when there are no
    # matches, since playlists[0] is undefined).
    with pytest.raises(RuntimeError):
        find_playlist_by_name(name)


# --- set_song_key ---


def test_set_song_key_passes_id_and_key_to_jxa():
    mock = MagicMock(returncode=0, stdout="null")
    with patch(
        "music_stuff.lib.lib_apple_music.subprocess.run", return_value=mock
    ) as mock_run:
        set_song_key("DEADBEEF", "6d")
    script = mock_run.call_args.kwargs["input"]
    assert json.dumps("DEADBEEF") in script
    assert json.dumps("6d") in script


def test_set_song_key_raises_on_error():
    mock = MagicMock(
        returncode=1, stderr="execution error: Comment contains more than a key (-2700)"
    )
    with patch("music_stuff.lib.lib_apple_music.subprocess.run", return_value=mock):
        with pytest.raises(RuntimeError, match="Comment contains more than a key"):
            set_song_key("DEADBEEF", "6d")


def test_run_jxa_raises_on_nonzero_returncode():
    mock = MagicMock(returncode=1, stderr="execution error: Error: test error (-2700)")
    with patch("music_stuff.lib.lib_apple_music.subprocess.run", return_value=mock):
        with pytest.raises(RuntimeError, match="test error"):
            find_songs_by_folder_name("Test Folder")


def test_find_song_by_id_passes_id_as_string_to_jxa():
    mock = MagicMock(returncode=0, stdout="null")
    with patch(
        "music_stuff.lib.lib_apple_music.subprocess.run", return_value=mock
    ) as mock_run:
        find_song_by_id("966EC6D01F2DED99")
    script = mock_run.call_args.kwargs["input"]
    assert json.dumps("966EC6D01F2DED99") in script


@needs_osascript
def test_find_playlist_by_name_not_unique():
    with pytest.raises(RuntimeError):
        find_playlist_by_name("Chillhop")


@needs_osascript
def test_find_playlist_by_name():
    playlist = find_playlist_by_name("Test Folder")
    assert "id" in playlist
    assert "name" in playlist
    assert "duration" in playlist
    assert "favorited" in playlist


@needs_osascript
def test_find_songs_by_folder_name():
    result = find_songs_by_folder_name("Test Folder")
    assert len(result) > 0
    assert isinstance(result[0], AppleMusicSong)
    assert any(s.name == "Sweet Unrest" for s in result)


@needs_osascript
def test_find_songs_by_playlist_name():
    result = find_songs_by_playlist_name("Ambiance")
    assert len(result) > 0
    assert isinstance(result[0], AppleMusicSong)


@needs_osascript
def test_find_song_by_id():
    """Look up songs by ID, including high-bit-set IDs."""
    songs = find_songs_by_folder_name("Test Folder")
    reference = next(s for s in songs if s.name == "Sweet Unrest")

    result = find_song_by_id(reference.id)
    assert result is not None
    assert isinstance(result, AppleMusicSong)
    assert result.name == "Sweet Unrest"
    assert result.id == reference.id

    # High-bit-set ID (was negative as signed int64)
    high_bit_ids = [s for s in songs if s.id[0] in "89ABCDEF"]
    if high_bit_ids:
        hb = find_song_by_id(high_bit_ids[0].id)
        assert hb is not None
        assert hb.id == high_bit_ids[0].id


@needs_osascript
def test_find_song_by_id_returns_none_when_not_found():
    result = find_song_by_id("FFFFFFFFFFFFFFFF")
    assert result is None


@needs_osascript
def test_set_song_bpm():
    songs = find_songs_by_folder_name("Test Folder")
    song = songs[0]
    original_bpm = song.bpm

    set_song_bpm(song.id, 999)
    updated = find_song_by_id(song.id)
    assert updated.bpm == 999

    set_song_bpm(song.id, original_bpm)
    restored = find_song_by_id(song.id)
    assert restored.bpm == original_bpm


@needs_osascript
def test_set_song_bpm_not_found():
    with pytest.raises(RuntimeError, match="Track not found"):
        set_song_bpm("FFFFFFFFFFFFFFFF", 120)
