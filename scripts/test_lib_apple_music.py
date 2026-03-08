import pytest
from unittest.mock import patch, MagicMock
from lib_apple_music import find_playlists, find_tracks_by_playlist


def test_run_jxa_raises_on_nonzero_returncode():
    mock = MagicMock(returncode=1, stderr="execution error: Error: test error (-2700)")
    with patch("lib_apple_music.subprocess.run", return_value=mock):
        with pytest.raises(RuntimeError, match="test error"):
            find_playlists()


def test_find_playlists():
    result = find_playlists()
    assert len(result) > 0
    assert any(pl["name"] == "Ambiance" for pl in result)


def test_find_tracks_by_playlist():
    result = find_tracks_by_playlist("Ambiance")
    assert len(result) > 0
    track = result[0]
    assert "name" in track
    assert "artist" in track
    assert "comment" in track
    assert "bpm" in track
    assert "location" in track
