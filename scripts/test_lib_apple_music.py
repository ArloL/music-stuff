import json
import pytest
from unittest.mock import patch, MagicMock
from lib_apple_music import find_playlist_by_name, find_tracks_by_playlist_name, find_tracks_by_folder_name, find_track_by_id, find_all_tracks


def test_run_jxa_raises_on_nonzero_returncode():
    mock = MagicMock(returncode=1, stderr="execution error: Error: test error (-2700)")
    with patch("lib_apple_music.subprocess.run", return_value=mock):
        with pytest.raises(RuntimeError, match="test error"):
            find_tracks_by_folder_name("Critical Mass")


def test_find_playlist_by_name_not_unique():
    with pytest.raises(RuntimeError):
        playlist = find_playlist_by_name("Chillhop")


def test_find_playlist_by_name():
    playlist = find_playlist_by_name("Critical Mass")
    assert "id" in playlist
    assert "name" in playlist
    assert "duration" in playlist
    assert "favorited" in playlist


def test_find_tracks_by_folder_name():
    result = find_tracks_by_folder_name("Critical Mass")
    assert len(result) > 0
    track = result[0]
    assert "name" in track
    assert "artist" in track
    assert "comment" in track
    assert "bpm" in track
    assert "location" in track
    assert any(t["name"] == "Little Space" for t in result)


def test_find_tracks_by_playlist_name():
    result = find_tracks_by_playlist_name("Ambiance")
    assert len(result) > 0
    track = result[0]
    assert "name" in track
    assert "artist" in track
    assert "comment" in track
    assert "bpm" in track
    assert "location" in track


def test_find_all_tracks():
    result = find_all_tracks()
    assert len(result) > 0
    track = result[0]
    assert "name" in track
    assert "artist" in track
    assert "comment" in track
    assert "bpm" in track
    assert "location" in track
    assert "persistentID" in track


def test_find_track_by_id_returns_correct_track():
    tracks = find_tracks_by_folder_name("Critical Mass")
    reference = next(t for t in tracks if t["name"] == "Little Space")
    track_id = reference["persistentID"]

    result = find_track_by_id(track_id)

    assert result is not None
    assert result["name"] == "Little Space"
    assert result["persistentID"] == track_id


def test_find_track_by_id_returns_correct_fields():
    tracks = find_tracks_by_folder_name("Critical Mass")
    track_id = tracks[0]["persistentID"]

    result = find_track_by_id(track_id)

    assert result is not None
    assert "name" in result
    assert "artist" in result
    assert "comment" in result
    assert "bpm" in result
    assert "location" in result
    assert "persistentID" in result


def test_find_track_by_id_returns_none_when_not_found():
    result = find_track_by_id("FFFFFFFFFFFFFFFF")
    assert result is None


def test_find_track_by_id_high_bit_set():
    # IDs starting with 8-F have the high bit set (were negative as signed int64)
    tracks = find_tracks_by_folder_name("Critical Mass")
    high_bit_ids = [t for t in tracks if t["persistentID"][0] in "89ABCDEF"]
    if not high_bit_ids:
        pytest.skip("No tracks with high-bit-set persistent IDs in Critical Mass")
    reference = high_bit_ids[0]
    track_id = reference["persistentID"]

    result = find_track_by_id(track_id)

    assert result is not None
    assert result["persistentID"] == track_id


def test_find_track_by_id_passes_id_as_string_to_jxa():
    # Ensures hex IDs are passed as strings to JXA
    mock = MagicMock(returncode=0, stdout="null")
    with patch("lib_apple_music.subprocess.run", return_value=mock) as mock_run:
        find_track_by_id("966EC6D01F2DED99")
    script = mock_run.call_args.kwargs["input"]
    assert json.dumps("966EC6D01F2DED99") in script
