import pytest
from unittest.mock import patch, MagicMock
from lib_apple_music import find_playlist_by_name, find_tracks_by_playlist_name, find_tracks_by_folder_name


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
