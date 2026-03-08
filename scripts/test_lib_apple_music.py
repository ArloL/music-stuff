import json
import pytest
from unittest.mock import patch, MagicMock
from lib_apple_music import find_playlist_by_name, find_tracks_by_playlist_name, find_tracks_by_folder_name, find_track_by_id


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


def test_find_track_by_id_returns_correct_track():
    tracks = find_tracks_by_folder_name("Critical Mass")
    reference = next(t for t in tracks if t["name"] == "Little Space")
    track_id = int(reference["persistentID"])

    result = find_track_by_id(track_id)

    assert result is not None
    assert result["name"] == "Little Space"
    assert int(result["persistentID"]) == track_id


def test_find_track_by_id_returns_correct_fields():
    tracks = find_tracks_by_folder_name("Critical Mass")
    track_id = int(tracks[0]["persistentID"])

    result = find_track_by_id(track_id)

    assert result is not None
    assert "name" in result
    assert "artist" in result
    assert "comment" in result
    assert "bpm" in result
    assert "location" in result
    assert "persistentID" in result


def test_find_track_by_id_returns_none_when_not_found():
    result = find_track_by_id(0)
    assert result is None


def test_find_track_by_id_negative_id():
    # Negative IDs are valid (high-bit unsigned 64-bit values stored as signed)
    tracks = find_tracks_by_folder_name("Critical Mass")
    negative_ids = [t for t in tracks if int(t["persistentID"]) < 0]
    if not negative_ids:
        pytest.skip("No tracks with negative persistent IDs in Critical Mass")
    reference = negative_ids[0]
    track_id = int(reference["persistentID"])

    result = find_track_by_id(track_id)

    assert result is not None
    assert int(result["persistentID"]) == track_id


def test_find_track_by_id_passes_id_as_string_to_jxa():
    # Ensures large 64-bit IDs are passed as strings, not JS numbers (which lose precision)
    mock = MagicMock(returncode=0, stdout="null")
    with patch("lib_apple_music.subprocess.run", return_value=mock) as mock_run:
        find_track_by_id(-7606924123403588199)
    script = mock_run.call_args.kwargs["input"]
    assert json.dumps(str(-7606924123403588199)) in script
