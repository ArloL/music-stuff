from music_stuff.lib.lib_spotify import (
    all_playlist_items,
    get_sp,
    replace_playlist_items,
    user_playlist_by_name,
)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Delete duplicates from a Spotify playlist"
    )
    parser.add_argument(
        "playlist_name", nargs="?", default="Would Play", help="Name of the playlist"
    )
    args = parser.parse_args()
    playlist_name = args.playlist_name
    sp = get_sp()

    playlist = user_playlist_by_name(sp, playlist_name)

    tracks = all_playlist_items(sp, playlist["id"])

    seen = set()
    deduped_uris = []

    for track in tracks:
        item = track["item"]
        if item is None:
            continue
        track_id = item["id"]
        if track_id not in seen:
            seen.add(track_id)
            deduped_uris.append(item["uri"])

    removed = len(tracks) - len(deduped_uris)
    if removed == 0:
        print("No duplicates found")
        return

    print(
        f"Found {removed} duplicates. Replacing playlist with {len(deduped_uris)} tracks..."
    )

    replace_playlist_items(sp, playlist["id"], deduped_uris)

    print("Done")


if __name__ == "__main__":
    main()
