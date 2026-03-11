import json
import pytest
from unittest.mock import patch, MagicMock
from lib_apple_music import find_playlist_by_name, find_songs_by_playlist_name, find_songs_by_folder_name, find_song_by_id, find_all_songs, set_song_bpm


def test_run_jxa_raises_on_nonzero_returncode():
    mock = MagicMock(returncode=1, stderr="execution error: Error: test error (-2700)")
    with patch("lib_apple_music.subprocess.run", return_value=mock):
        with pytest.raises(RuntimeError, match="test error"):
            find_songs_by_folder_name("Critical Mass")


def test_find_playlist_by_name_not_unique():
    with pytest.raises(RuntimeError):
        playlist = find_playlist_by_name("Chillhop")


def test_find_playlist_by_name():
    playlist = find_playlist_by_name("Critical Mass")
    assert "id" in playlist
    assert "name" in playlist
    assert "duration" in playlist
    assert "favorited" in playlist


def test_find_songs_by_folder_name():
    result = find_songs_by_folder_name("Critical Mass")
    assert len(result) > 0
    song = result[0]
    assert "name" in song
    assert "artist" in song
    assert "comment" in song
    assert "bpm" in song
    assert "location" in song
    assert any(s["name"] == "Little Space" for s in result)


def test_find_songs_by_playlist_name():
    result = find_songs_by_playlist_name("Ambiance")
    assert len(result) > 0
    song = result[0]
    assert "name" in song
    assert "artist" in song
    assert "comment" in song
    assert "bpm" in song
    assert "location" in song


def test_find_all_songs():
    result = find_all_songs()
    assert len(result) > 0
    song = result[0]
    assert "name" in song
    assert "artist" in song
    assert "comment" in song
    assert "bpm" in song
    assert "location" in song
    assert "persistentID" in song


def test_find_song_by_id_returns_correct_song():
    songs = find_songs_by_folder_name("Critical Mass")
    reference = next(s for s in songs if s["name"] == "Little Space")
    song_id = reference["persistentID"]

    result = find_song_by_id(song_id)

    assert result is not None
    assert result["name"] == "Little Space"
    assert result["persistentID"] == song_id


def test_find_song_by_id_returns_correct_fields():
    songs = find_songs_by_folder_name("Critical Mass")
    song_id = songs[0]["persistentID"]

    result = find_song_by_id(song_id)

    assert result is not None
    assert "name" in result
    assert "artist" in result
    assert "comment" in result
    assert "bpm" in result
    assert "location" in result
    assert "persistentID" in result


def test_find_song_by_id_returns_none_when_not_found():
    result = find_song_by_id("FFFFFFFFFFFFFFFF")
    assert result is None


def test_find_song_by_id_high_bit_set():
    # IDs starting with 8-F have the high bit set (were negative as signed int64)
    songs = find_songs_by_folder_name("Critical Mass")
    high_bit_ids = [s for s in songs if s["persistentID"][0] in "89ABCDEF"]
    if not high_bit_ids:
        pytest.skip("No songs with high-bit-set persistent IDs in Critical Mass")
    reference = high_bit_ids[0]
    song_id = reference["persistentID"]

    result = find_song_by_id(song_id)

    assert result is not None
    assert result["persistentID"] == song_id


def test_find_song_by_id_passes_id_as_string_to_jxa():
    # Ensures hex IDs are passed as strings to JXA
    mock = MagicMock(returncode=0, stdout="null")
    with patch("lib_apple_music.subprocess.run", return_value=mock) as mock_run:
        find_song_by_id("966EC6D01F2DED99")
    script = mock_run.call_args.kwargs["input"]
    assert json.dumps("966EC6D01F2DED99") in script


def test_set_song_bpm():
    songs = find_songs_by_folder_name("Critical Mass")
    song = songs[0]
    original_bpm = song["bpm"]

    set_song_bpm(song["persistentID"], 999)
    updated = find_song_by_id(song["persistentID"])
    assert updated["bpm"] == 999

    set_song_bpm(song["persistentID"], original_bpm)
    restored = find_song_by_id(song["persistentID"])
    assert restored["bpm"] == original_bpm


def test_set_song_bpm_not_found():
    with pytest.raises(RuntimeError, match="Track not found"):
        set_song_bpm("FFFFFFFFFFFFFFFF", 120)
