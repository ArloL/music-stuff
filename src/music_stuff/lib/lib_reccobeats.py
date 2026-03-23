"""Reccobeats API client with local CSV cache."""

import csv
import json
from pathlib import Path
from urllib.parse import urlparse

import requests


RECCOBEATS_CACHE_PATH = Path(__file__).parent.parent.parent.parent / "data" / "lib_reccobeats_cache.csv"

_CACHE_FIELDNAMES = [
    "spotify_id", "reccobeats_id", "mode", "key", "tempo",
    "acousticness", "danceability", "energy", "instrumentalness",
    "liveness", "loudness", "speechiness", "valence",
]

_SPOTIFY_MAJOR_TO_OPEN_KEY = {
    0: "1d", 7: "2d", 2: "3d", 9: "4d", 4: "5d", 11: "6d",
    6: "7d", 1: "8d", 8: "9d", 3: "10d", 10: "11d", 5: "12d",
}
_SPOTIFY_MINOR_TO_OPEN_KEY = {
    9: "1m", 4: "2m", 11: "3m", 6: "4m", 1: "5m", 8: "6m",
    3: "7m", 10: "8m", 5: "9m", 0: "10m", 7: "11m", 2: "12m",
}

# Moved here from spotify_playlist_to_csv.py for shared use.
SPOTIFY_TO_BEATUNES_KEY_MAP = {
    (-1, -1): -1,  # no key detected
    (0, 1): 10,    # ??: ??
    (0, 2): 24,    # 7A: Pavla, Noura - Don't Owe Me a Thing
    (0, 3): 14,    # 2A: ??
    (0, 4): 4,     # 9A: DAMH - Black Night
    (0, 5): 18,    # 4A: Jamie xx - Sleep Sound
    (0, 6): 8,     # 11A: Youandewan - 1988 - Original Mix
    (0, 7): 22,    # 6A: Guy Gerber, &ME - What To Do - &ME Remix
    (0, 8): 12,    # ??: ??
    (0, 9): 2,     # 8A: Dorisburg - Emotion - Original
    (0, 10): 16,   # 3A: Leon Vynehall - Butterflies
    (0, 11): 6,    # 10A: Robag Wruhme als Die Dub Rolle - Lampetee
    (1, 0): 1,     # 8B: Axel Boman - Purple Drank
    (1, 1): 15,    # 3B: Todd Terje - Ragysh
    (1, 2): 5,     # 10B: Daniel Bortz - Wohin Willst Du?
    (1, 3): 19,    # ??: ??
    (1, 4): 9,     # ??: ??
    (1, 5): 23,    # ??: Albion, Oliver Lieb - Air - Oliver Lieb Remix
    (1, 6): 13,    # 2B: Luvless - Luvmaschine
    (1, 7): 3,     # ??: DJ Koze - I Want To Sleep
    (1, 8): 17,    # 4B: DJ Seinfeld - U
    (1, 9): 7,     # ??: Map.ache - Thank U Again
    (1, 10): 21,   # ??: Jeigo - Pearl Leaf
    (1, 11): 11,   # ??: ??
}


def spotify_key_to_open_key(mode: int, key: int) -> str:
    """Convert Spotify mode/key integers to Open Key notation."""
    if mode == 1:
        return _SPOTIFY_MAJOR_TO_OPEN_KEY.get(key, "")
    else:
        return _SPOTIFY_MINOR_TO_OPEN_KEY.get(key, "")


def _coerce(v: str):
    try:
        return float(v)
    except (ValueError, TypeError):
        return v


def _load_cache() -> dict[str, dict]:
    """Returns {spotify_id: {reccobeats_id, mode, key, tempo, ...}}."""
    if not RECCOBEATS_CACHE_PATH.exists():
        return {}
    with open(RECCOBEATS_CACHE_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "spotify_id" not in reader.fieldnames:
            return {}
        return {
            row["spotify_id"]: {k: _coerce(v) for k, v in row.items() if k != "spotify_id"}
            for row in reader
        }


def _write_cache(cache: dict[str, dict]) -> None:
    """Write cache CSV sorted by spotify_id with LF line endings."""
    fieldnames = ["spotify_id"]
    seen: set[str] = set()
    for entry in cache.values():
        for k in entry:
            if k not in seen:
                fieldnames.append(k)
                seen.add(k)
    with open(RECCOBEATS_CACHE_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore", lineterminator='\n')
        writer.writeheader()
        for sid in sorted(cache):
            writer.writerow({"spotify_id": sid, **cache[sid]})


def get_audio_features(spotify_ids: list[str]) -> dict[str, dict]:
    """Batch fetch audio features, serves cache-first. Fetches missing in chunks of 40.

    Failed chunks are skipped with a warning; successfully fetched IDs are cached and returned.
    """
    cache = _load_cache()
    missing = [sid for sid in spotify_ids if sid not in cache]
    for i in range(0, len(missing), 40):
        chunk = missing[i:i + 40]
        try:
            response = requests.get(
                'https://api.reccobeats.com/v1/audio-features',
                headers={'Accept': 'application/json'},
                params={'ids': chunk},
            )
            response.raise_for_status()
            data = response.json()
            if 'content' not in data:
                print(f"  Warning: reccobeats response missing 'content' for chunk {i // 100 + 1}: {data}")
                continue
            for feature in data['content']:
                href = feature.get('href', '')
                if not href:
                    continue
                spotify_id = urlparse(href).path.split("/")[-1]
                feature['spotify_id'] = spotify_id
                cache[spotify_id] = feature
            _write_cache(cache)
        except requests.exceptions.RequestException as exc:
            print(f"  Warning: reccobeats request failed for chunk {i // 100 + 1}: {exc}")
        except (KeyError, ValueError) as exc:
            print(f"  Warning: reccobeats response parse error for chunk {i // 100 + 1}: {exc}")
    return {sid: cache[sid] for sid in spotify_ids if sid in cache}


def get_recommendation(spotify_or_reccobeats_id: str) -> list[dict]:
    response = requests.get(
        'https://api.reccobeats.com/v1/track/recommendation',
        headers={'Accept': 'application/json'},
        params={'size': 5, 'seeds': [spotify_or_reccobeats_id]},
    )
    response.raise_for_status()
    return response.json()['content']


def get_reccobeats_id(spotify_id: str) -> str:
    response = requests.get(
        'https://api.reccobeats.com/v1/audio-features',
        headers={'Accept': 'application/json'},
        params={'ids': spotify_id},
    )
    response.raise_for_status()
    content = response.json().get('content', [])
    if not content:
        raise ValueError(f"No reccobeats entry found for spotify_id={spotify_id!r}")
    return content[0]['id']


def get_track_detail(reccobeats_id: str) -> dict:
    response = requests.get(
        f'https://api.reccobeats.com/v1/track/{reccobeats_id}',
        headers={'Accept': 'application/json'},
    )
    response.raise_for_status()
    return response.json()
