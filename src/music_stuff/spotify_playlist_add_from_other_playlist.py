from music_stuff.lib.lib_spotify import (
    all_playlist_items,
    get_sp,
    user_playlist_by_name,
)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Add all tracks from one playlist to another"
    )
    parser.add_argument(
        "target_playlist_name",
        nargs="?",
        default="Recommended",
        help="The playlist which will have songs added",
    )
    parser.add_argument(
        "source_playlist_name",
        nargs="?",
        default="Gerd Janson's track IDs",
        help="The playlist which indicates the songs that should be removed",
    )
    args = parser.parse_args()

    sp = get_sp()

    target_playlist = user_playlist_by_name(sp, args.target_playlist_name)
    source_playlist = user_playlist_by_name(sp, args.source_playlist_name)

    tracks = all_playlist_items(sp, source_playlist["id"])
    track_ids = [f"spotify:track:{t['item']['id']}" for t in tracks if t.get("item")]

    for i in range(0, len(track_ids), 100):
        sp.playlist_add_items(target_playlist["id"], track_ids[i : i + 100])


if __name__ == "__main__":
    main()
