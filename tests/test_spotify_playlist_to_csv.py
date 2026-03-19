import json
from unittest.mock import patch, MagicMock

from music_stuff.spotify_playlist_to_csv import get_audio_features


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


def test_get_audio_features_single_chunk():
    ids = [f"id{i}" for i in range(5)]
    features = [_make_feature(sid) for sid in ids]

    with patch("music_stuff.spotify_playlist_to_csv.requests.get") as mock_get:
        mock_get.return_value.text = json.dumps({"content": features})
        result = get_audio_features(ids)

    mock_get.assert_called_once()
    assert [r["spotify_id"] for r in result] == ids


def test_get_audio_features_chunks_at_100():
    ids = [f"id{i}" for i in range(150)]

    def fake_get(url, headers, params):
        chunk = params["ids"]
        resp = MagicMock()
        resp.text = json.dumps({"content": [_make_feature(sid) for sid in chunk]})
        return resp

    with patch("music_stuff.spotify_playlist_to_csv.requests.get", side_effect=fake_get) as mock_get:
        result = get_audio_features(ids)

    assert mock_get.call_count == 2
    first_call_ids = mock_get.call_args_list[0].kwargs["params"]["ids"]
    second_call_ids = mock_get.call_args_list[1].kwargs["params"]["ids"]
    assert len(first_call_ids) == 100
    assert len(second_call_ids) == 50
    assert [r["spotify_id"] for r in result] == ids
