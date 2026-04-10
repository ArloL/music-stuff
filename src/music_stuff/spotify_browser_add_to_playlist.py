import argparse

from music_stuff.lib.lib_spotify import get_sp, user_playlist_by_name
from music_stuff.lib.lib_spotify_browser import copy_playlist_via_browser


def _resolve_source_id(sp, arg: str) -> str:
    if arg.startswith("id:"):
        return arg[3:]
    return user_playlist_by_name(sp, arg)["id"]


def _resolve_target_name(sp, arg: str) -> str:
    if arg.startswith("id:"):
        return sp.playlist(arg[3:])["name"]
    return arg


def main():
    parser = argparse.ArgumentParser(
        description="Copy all tracks from one playlist to another via the Spotify Web UI."
    )
    parser.add_argument("target_playlist", help="Playlist name or 'id:<spotify_id>'")
    parser.add_argument(
        "source_playlist", nargs="+", help="Playlist name(s) or 'id:<spotify_id>'"
    )
    parser.add_argument(
        "--recommendations",
        type=int,
        default=0,
        help="Add this many recommendation rows (data-testid='recommended-track') instead of playlist tracks",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode (no visible window)",
    )
    args = parser.parse_args()

    sp = get_sp()
    target_name = _resolve_target_name(sp, args.target_playlist)
    source_ids = [_resolve_source_id(sp, s) for s in args.source_playlist]

    copy_playlist_via_browser(
        source_playlist_ids=source_ids,
        target_playlist_name=target_name,
        recommendations=args.recommendations,
        headless=args.headless,
    )
    label = "Recommendations from" if args.recommendations > 0 else "Tracks from"
    for source in args.source_playlist:
        print(f"Done. {label} '{source}' added to '{args.target_playlist}'.")


if __name__ == "__main__":
    main()
