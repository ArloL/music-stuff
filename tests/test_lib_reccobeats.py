from unittest.mock import MagicMock, patch

from music_stuff.lib.lib_reccobeats import (
    _load_cache,
    _write_cache,
    spotify_key_to_open_key,
)

# --- spotify_key_to_open_key ---


def test_spotify_key_to_open_key_major():
    # mode=1 => major
    assert spotify_key_to_open_key(1, 0) == "1d"  # C major
    assert spotify_key_to_open_key(1, 7) == "2d"  # G major
    assert spotify_key_to_open_key(1, 9) == "4d"  # A major
    assert spotify_key_to_open_key(1, 5) == "12d"  # F major


def test_spotify_key_to_open_key_minor():
    # mode=0 => minor
    assert spotify_key_to_open_key(0, 9) == "1m"  # A minor
    assert spotify_key_to_open_key(0, 4) == "2m"  # E minor
    assert spotify_key_to_open_key(0, 0) == "10m"  # C minor
    assert spotify_key_to_open_key(0, 2) == "12m"  # D minor


def test_spotify_key_to_open_key_unknown_returns_empty():
    assert spotify_key_to_open_key(1, 99) == ""
    assert spotify_key_to_open_key(0, 99) == ""


# --- cache round trip ---


def test_cache_round_trip(tmp_path):
    cache_path = tmp_path / "lib_reccobeats_cache.csv"
    cache = {
        "spotify123": {
            "reccobeats_id": "rb456",
            "mode": 1.0,
            "key": 0.0,
            "tempo": 128.5,
        },
        "spotify789": {
            "reccobeats_id": "rb012",
            "mode": 0.0,
            "key": 9.0,
            "tempo": 95.0,
        },
    }

    with patch("music_stuff.lib.lib_reccobeats.RECCOBEATS_CACHE_PATH", cache_path):
        _write_cache(cache)
        loaded = _load_cache()

    assert set(loaded.keys()) == {"spotify123", "spotify789"}
    assert loaded["spotify123"]["tempo"] == 128.5
    assert loaded["spotify789"]["mode"] == 0.0


def test_cache_missing_file_returns_empty(tmp_path):
    with patch(
        "music_stuff.lib.lib_reccobeats.RECCOBEATS_CACHE_PATH",
        tmp_path / "nonexistent.csv",
    ):
        assert _load_cache() == {}


def test_cache_writes_sorted_by_id(tmp_path):
    cache_path = tmp_path / "lib_reccobeats_cache.csv"
    cache = {
        "zzz_spotify": {"tempo": 100.0},
        "aaa_spotify": {"tempo": 120.0},
    }

    with patch("music_stuff.lib.lib_reccobeats.RECCOBEATS_CACHE_PATH", cache_path):
        _write_cache(cache)

    lines = cache_path.read_text().splitlines()
    assert "aaa_spotify" in lines[1]
    assert "zzz_spotify" in lines[2]


# --- get_audio_features ---


def test_get_audio_features_uses_cache(tmp_path):
    """Cached IDs should not trigger any HTTP requests."""
    cache_path = tmp_path / "lib_reccobeats_cache.csv"
    cache = {
        "cached_id": {"reccobeats_id": "rb1", "mode": 1.0, "key": 0.0, "tempo": 120.0},
    }

    with patch("music_stuff.lib.lib_reccobeats.RECCOBEATS_CACHE_PATH", cache_path):
        _write_cache(cache)

        with patch("music_stuff.lib.lib_reccobeats.requests.get") as mock_get:
            from music_stuff.lib.lib_reccobeats import get_audio_features

            result = get_audio_features(["cached_id"])
            mock_get.assert_not_called()

    assert "cached_id" in result
    assert result["cached_id"]["tempo"] == 120.0


def test_get_audio_features_fetches_missing(tmp_path):
    """IDs not in cache should trigger an HTTP request."""
    cache_path = tmp_path / "lib_reccobeats_cache.csv"

    api_response = {
        "content": [
            {
                "id": "rb_new",
                "href": "https://api.reccobeats.com/v1/track/new_spotify_id",
                "mode": 1,
                "key": 7,
                "tempo": 130.0,
            }
        ]
    }

    mock_response = MagicMock()
    mock_response.json.return_value = api_response

    with patch("music_stuff.lib.lib_reccobeats.RECCOBEATS_CACHE_PATH", cache_path):
        with patch(
            "music_stuff.lib.lib_reccobeats.requests.get", return_value=mock_response
        ) as mock_get:
            from music_stuff.lib.lib_reccobeats import get_audio_features

            result = get_audio_features(["new_spotify_id"])
            mock_get.assert_called_once()

    assert "new_spotify_id" in result
    assert result["new_spotify_id"]["tempo"] == 130.0
