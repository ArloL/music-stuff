from unittest.mock import patch, MagicMock

from music_stuff.lib.lib_reccobeats import get_audio_features


def _make_feature(spotify_id):
    return {
        "href": f"https://api.reccobeats.com/v1/audio-features/{spotify_id}",
        "id": spotify_id,
        "mode": 1,
        "key": 0,
        "tempo": 128.0,
        "acousticness": 0.1,
        "danceability": 0.8,
        "energy": 0.9,
        "instrumentalness": 0.5,
        "liveness": 0.1,
        "loudness": -5.0,
        "speechiness": 0.05,
        "valence": 0.7,
    }


def test_get_audio_features_single_chunk(tmp_path):
    ids = [f"id{i}" for i in range(5)]
    features = [_make_feature(sid) for sid in ids]

    with patch("music_stuff.lib.lib_reccobeats.RECCOBEATS_CACHE_PATH", tmp_path / "cache.csv"):
        with patch("music_stuff.lib.lib_reccobeats.requests.get") as mock_get:
            mock_get.return_value.json.return_value = {"content": features}
            result = get_audio_features(ids)

    mock_get.assert_called_once()
    assert set(result.keys()) == set(ids)
    assert all(r["spotify_id"] == sid for sid, r in result.items())


def test_get_audio_features_chunks_at_40(tmp_path):
    ids = [f"id{i}" for i in range(90)]

    def fake_get(url, headers, params):
        chunk = params["ids"]
        resp = MagicMock()
        resp.json.return_value = {"content": [_make_feature(sid) for sid in chunk]}
        return resp

    with patch("music_stuff.lib.lib_reccobeats.RECCOBEATS_CACHE_PATH", tmp_path / "cache.csv"):
        with patch("music_stuff.lib.lib_reccobeats.requests.get", side_effect=fake_get) as mock_get:
            result = get_audio_features(ids)

    assert mock_get.call_count == 3
    assert len(mock_get.call_args_list[0].kwargs["params"]["ids"]) == 40
    assert len(mock_get.call_args_list[1].kwargs["params"]["ids"]) == 40
    assert len(mock_get.call_args_list[2].kwargs["params"]["ids"]) == 10
    assert set(result.keys()) == set(ids)
