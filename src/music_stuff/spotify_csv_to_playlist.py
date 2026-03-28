from pathlib import Path

import pandas as pd

from music_stuff.lib.lib_spotify import all_playlist_items, get_playlist_id, get_sp

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

    parser = argparse.ArgumentParser(
        description="Add all tracks from a csv to a spotify playlist"
    )
    parser.add_argument(
        "source_csv",
        type=str,
        help="Source csv",
    )
    parser.add_argument(
        "target_playlist",
        type=str,
        help="Playlist name or 'id:<spotify_id>'",
    )
    args = parser.parse_args()

    sp = get_sp()
    spotify_mapping = pd.read_csv(ROOT_DIR / "data/spotify-mapping.csv").set_index(
        "apple_music_id"
    )

    playlist_id = get_playlist_id(sp, args.target_playlist)
    tracks = all_playlist_items(sp, playlist_id)

    df = pd.read_csv(ROOT_DIR / args.source_csv)

    existing_ids = {track["item"]["id"] for track in tracks if track.get("item")}
    to_add = []
    for i, song in df.iterrows():
        spotify_id = find_spotify_id_for_song(sp, song, spotify_mapping)
        if spotify_id == "-1":
            print(f"No spotify ID for {song['artist']} - {song['name']}")
        elif spotify_id in existing_ids:
            print(f"Already in the playlist {song['artist']} - {song['name']}")
        else:
            print(f"Adding {song['artist']} - {song['name']}")
            to_add.append(f"spotify:track:{spotify_id}")

    for i in range(0, len(to_add), 100):
        sp.playlist_add_items(playlist_id, to_add[i : i + 100])


if __name__ == "__main__":
    main()
