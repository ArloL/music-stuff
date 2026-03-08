import os
import subprocess
import json

_JS_FILE = os.path.join(os.path.dirname(__file__), "lib_apple_music_jxa.js")


def _run_jxa(call: str):
    with open(_JS_FILE) as f:
        script = f.read() + f"\nJSON.stringify({call})"
    result = subprocess.run(
        ["osascript", "-l", "JavaScript"],
        input=script,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return json.loads(result.stdout)


def find_playlists() -> list[dict]:
    return _run_jxa("findPlaylists()")


def find_tracks_by_playlist(playlist_name: str) -> list[dict]:
    return _run_jxa(f"findTracksByPlaylist({json.dumps(playlist_name)})")


def find_tracks_by_folder(folder_name: str) -> list[dict]:
    return _run_jxa(f"findTracksByFolder({json.dumps(folder_name)})")


def find_all_tracks() -> list[dict]:
    return _run_jxa("findAllTracks()")
