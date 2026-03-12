import json
import shutil

import pytest
from unittest.mock import patch, MagicMock
from music_stuff.lib.lib_apple_music import (
    AppleMusicSong,
    find_playlist_by_name,
    find_songs_by_playlist_name,
    find_songs_by_folder_name,
    find_song_by_id,
    set_song_bpm,
)

needs_osascript = pytest.mark.skipif(
    shutil.which("osascript") is None,
    reason="osascript not available",
)


def test_run_jxa_raises_on_nonzero_returncode():
    mock = MagicMock(returncode=1, stderr="execution error: Error: test error (-2700)")
    with patch("music_stuff.lib.lib_apple_music.subprocess.run", return_value=mock):
        with pytest.raises(RuntimeError, match="test error"):
            find_songs_by_folder_name("Test Folder")


def test_find_song_by_id_passes_id_as_string_to_jxa():
    mock = MagicMock(returncode=0, stdout="null")
    with patch("music_stuff.lib.lib_apple_music.subprocess.run", return_value=mock) as mock_run:
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

    result = find_song_by_id(reference.persistentID)
    assert result is not None
    assert isinstance(result, AppleMusicSong)
    assert result.name == "Sweet Unrest"
    assert result.persistentID == reference.persistentID

    # High-bit-set ID (was negative as signed int64)
    high_bit_ids = [s for s in songs if s.persistentID[0] in "89ABCDEF"]
    if high_bit_ids:
        hb = find_song_by_id(high_bit_ids[0].persistentID)
        assert hb is not None
        assert hb.persistentID == high_bit_ids[0].persistentID


@needs_osascript
def test_find_song_by_id_returns_none_when_not_found():
    result = find_song_by_id("FFFFFFFFFFFFFFFF")
    assert result is None


@needs_osascript
def test_set_song_bpm():
    songs = find_songs_by_folder_name("Test Folder")
    song = songs[0]
    original_bpm = song.bpm

    set_song_bpm(song.persistentID, 999)
    updated = find_song_by_id(song.persistentID)
    assert updated.bpm == 999

    set_song_bpm(song.persistentID, original_bpm)
    restored = find_song_by_id(song.persistentID)
    assert restored.bpm == original_bpm


@needs_osascript
def test_set_song_bpm_not_found():
    with pytest.raises(RuntimeError, match="Track not found"):
        set_song_bpm("FFFFFFFFFFFFFFFF", 120)
