import os
import subprocess
import json
from dataclasses import dataclass

_JS_FILE = os.path.join(os.path.dirname(__file__), "lib_apple_music_jxa.js")
_js_source: str | None = None


@dataclass
class AppleMusicSong:
    persistentID: str
    name: str
    artist: str
    comment: str
    bpm: int
    location: str
    rating: int = 0
    genre: str = ""
    persistentIdAsInt: int = 0
    beatunesId: int = 0


def _to_song(raw: dict) -> AppleMusicSong:
    return AppleMusicSong(
        persistentID=raw["persistentID"],
        name=raw.get("name", ""),
        artist=raw.get("artist", ""),
        comment=raw.get("comment", ""),
        bpm=raw.get("bpm", 0),
        location=raw.get("location", ""),
        rating=raw.get("rating", 0),
        genre=raw.get("genre", ""),
        persistentIdAsInt=int(raw["persistentIdAsInt"]) if raw.get("persistentIdAsInt") else 0,
        beatunesId=int(raw["beatunesId"]) if raw.get("beatunesId") else 0,
    )


def _load_js_source() -> str:
    global _js_source
    if _js_source is None:
        with open(_JS_FILE) as f:
            _js_source = f.read()
    return _js_source


def _run_jxa(call: str):
    script = _load_js_source() + f"\nJSON.stringify({call})"
    result = subprocess.run(
        ["osascript", "-l", "JavaScript"],
        input=script,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return json.loads(result.stdout)


def find_playlist_by_name(playlist_name: str) -> dict:
    return _run_jxa(f"findPlaylistByName({json.dumps(playlist_name)})")


def find_songs_by_folder_name(folder_name: str) -> list[AppleMusicSong]:
    return [_to_song(r) for r in _run_jxa(f"findTracksByFolderName({json.dumps(folder_name)})")]


def find_songs_by_playlist_name(playlist_name: str) -> list[AppleMusicSong]:
    return [_to_song(r) for r in _run_jxa(f"findTracksByPlaylistName({json.dumps(playlist_name)})")]


def find_song_by_id(song_id: str) -> AppleMusicSong | None:
    raw = _run_jxa(f"findTrackById({json.dumps(song_id)})")
    return _to_song(raw) if raw is not None else None


def find_all_songs() -> list[AppleMusicSong]:
    return [_to_song(r) for r in _run_jxa("findAllTracks()")]


def set_song_bpm(song_id: str, bpm: int) -> None:
    _run_jxa(f"setTrackBpm({json.dumps(song_id)}, {json.dumps(bpm)})")
