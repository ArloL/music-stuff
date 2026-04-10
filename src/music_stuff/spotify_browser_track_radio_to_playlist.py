import argparse

from music_stuff.lib.lib_spotify import all_playlist_items, get_playlist_id, get_sp
from music_stuff.lib.lib_spotify_browser import copy_track_radios_via_browser


def _resolve_target_name(sp, arg: str) -> str:
    if arg.startswith("id:"):
        return sp.playlist(arg[3:])["name"]
    return arg


def main():
    parser = argparse.ArgumentParser(
        description="For each track in a source playlist, add its song radio tracks to a target playlist via the Spotify Web UI."
    )
    parser.add_argument("target_playlist", help="Playlist name or 'id:<spotify_id>'")
    parser.add_argument(
        "source_playlist", help="Playlist name or 'id:<spotify_id>' to read tracks from"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode (no visible window)",
    )
    args = parser.parse_args()

    sp = get_sp()
    target_name = _resolve_target_name(sp, args.target_playlist)
    source_id = get_playlist_id(sp, args.source_playlist)

    items = all_playlist_items(sp, source_id)
    track_ids = [item["item"]["id"] for item in items]

    copy_track_radios_via_browser(
        track_ids=track_ids,
        target_playlist_name=target_name,
        headless=args.headless,
    )
    print(
        f"Done. Song radio for {len(track_ids)} tracks from '{args.source_playlist}' added to '{args.target_playlist}'."
    )


if __name__ == "__main__":
    main()
