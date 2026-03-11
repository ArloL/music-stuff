import os
import subprocess
import json

_JS_FILE = os.path.join(os.path.dirname(__file__), "lib_apple_music_jxa.js")
_js_source: str | None = None


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


def find_playlist_by_name(playlist_name: str) -> list[dict]:
    return _run_jxa(f"findPlaylistByName({json.dumps(playlist_name)})")


def find_songs_by_folder_name(folder_name: str) -> list[dict]:
    return _run_jxa(f"findTracksByFolderName({json.dumps(folder_name)})")


def find_songs_by_playlist_name(playlist_name: str) -> list[dict]:
    return _run_jxa(f"findTracksByPlaylistName({json.dumps(playlist_name)})")


def find_song_by_id(song_id: str) -> dict | None:
    return _run_jxa(f"findTrackById({json.dumps(song_id)})")


def find_all_songs() -> list[dict]:
    return _run_jxa("findAllTracks()")


def set_song_bpm(song_id: str, bpm: int) -> None:
    _run_jxa(f"setTrackBpm({json.dumps(song_id)}, {json.dumps(bpm)})")
