from music_stuff.lib.lib_spotify import (
    all_playlist_items,
    get_sp,
    user_playlist_by_name,
)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Delete duplicates from a Spotify playlist"
    )
    parser.add_argument(
        "delete_playlist_name",
        nargs="?",
        default="Recommended",
        help="The playlist which will have songs removed",
    )
    parser.add_argument(
        "source_playlist_name",
        nargs="?",
        default="Would Play",
        help="The playlist which indicates the songs that should be removed",
    )
    args = parser.parse_args()

    sp = get_sp()

    delete_playlist = user_playlist_by_name(sp, args.delete_playlist_name)
    source_playlist_id = user_playlist_by_name(sp, args.source_playlist_name)["id"]

    delete_tracks = all_playlist_items(sp, delete_playlist["id"])
    source_tracks = all_playlist_items(sp, source_playlist_id)

    source_ids = {t["item"]["id"] for t in source_tracks}
    items_to_delete = []

    for i, track in enumerate(delete_tracks):
        track_id = track["item"]["id"]
        if track_id in source_ids:
            print(f"Removing {i} {track_id}")
            items_to_delete.append(track_id)

    for i in range(0, len(items_to_delete), 100):
        sp.playlist_remove_all_occurrences_of_items(
            delete_playlist["id"], items_to_delete[i : i + 100]
        )


if __name__ == "__main__":
    main()
