from pathlib import Path

import pandas as pd

from music_stuff.lib.lib_spotify import (
    all_playlist_items,
    get_playlist_id,
    get_sp,
    replace_playlist_items,
)

ROOT_DIR = Path(__file__).parent.parent.parent


def find_spotify_id_for_artist_name(sp, artist, name, spotify_mapping):
    query = f"{artist} {name}"
    results = sp.search(query)
    tracks = results["tracks"]["items"]
    return tracks[0]["id"]


def find_spotify_id_for_song(sp, song, spotify_mapping):
    amid = song["apple_music_id"]
    if amid in spotify_mapping.index:
        return spotify_mapping.loc[amid, "spotify_id"]
    else:
        spotify_id = find_spotify_id_for_artist_name(
            sp, song["artist"], song["name"], spotify_mapping
        )
        spotify_mapping.loc[amid] = {"spotify_id": spotify_id}
        spotify_mapping.to_csv(
            ROOT_DIR / "data/spotify-mapping.csv",
            index_label="apple_music_id",
            lineterminator="\n",
        )
        return spotify_id


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Make a spotify playlist match a csv")
    parser.add_argument(
        "source_csv",
        type=str,
        nargs="?",
        default="./data/songs-would-play.csv",
        help="Source csv",
    )
    parser.add_argument(
        "target_playlist",
        type=str,
        nargs="?",
        default="Would Play",
        help="Playlist name or 'id:<spotify_id>'",
    )
    parser.add_argument("--dry-run", action="store_true", help="Only print the changes")
    args = parser.parse_args()

    sp = get_sp()
    spotify_mapping = pd.read_csv(ROOT_DIR / "data/spotify-mapping.csv").set_index(
        "apple_music_id"
    )

    playlist_id = get_playlist_id(sp, args.target_playlist)
    tracks = all_playlist_items(sp, playlist_id)

    df = pd.read_csv(ROOT_DIR / args.source_csv)

    current = [t["item"] for t in tracks if t.get("item")]
    desired = []
    labels = {}
    for _, song in df.iterrows():
        spotify_id = find_spotify_id_for_song(sp, song, spotify_mapping)
        if spotify_id == "-1":
            print(f"No spotify ID for {song['artist']} - {song['name']}")
        else:
            uri = f"spotify:track:{spotify_id}"
            if uri not in desired:
                desired.append(uri)
                labels[uri] = f"{song['artist']} - {song['name']}"

    current_uris = [item["uri"] for item in current]
    if current_uris == desired:
        print("Already matches")
        return

    for item in current:
        if item["uri"] not in desired:
            print(f"Removing {item['artists'][0]['name']} - {item['name']}")
    for uri in desired:
        if uri not in current_uris:
            print(f"Adding {labels[uri]}")
    if args.dry_run:
        return
    replace_playlist_items(sp, playlist_id, desired)
    print(f"Playlist now has {len(desired)} tracks")


if __name__ == "__main__":
    main()
