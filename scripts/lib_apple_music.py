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


def find_playlist_by_name(playlist_name: str) -> list[dict]:
    return _run_jxa(f"findPlaylistByName({json.dumps(playlist_name)})")


def find_tracks_by_folder_name(folder_name: str) -> list[dict]:
    return _run_jxa(f"findTracksByFolderName({json.dumps(folder_name)})")


def find_tracks_by_playlist_name(playlist_name: str) -> list[dict]:
    return _run_jxa(f"findTracksByPlaylistName({json.dumps(playlist_name)})")


def find_track_by_id(track_id: int) -> dict | None:
    return _run_jxa(f"findTrackById({json.dumps(str(track_id))})")


def find_all_tracks() -> list[dict]:
    return _run_jxa("findAllTracks()")
