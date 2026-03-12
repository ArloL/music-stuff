import json
import requests
import pandas as pd
from pathlib import Path
from urllib.parse import urlparse
from music_stuff.lib.lib_spotify import get_sp

DATA_DIR = Path(__file__).parent.parent.parent / "data"


def find_spotify_id_for_artist_name(sp, artist, name, spotify_mapping):
    query = f"{artist} {name}"
    results = sp.search(query)
    tracks = results['tracks']['items']
    return tracks[0]['id']

def find_spotify_id_for_song(sp, song, spotify_mapping):
    amid = song['apple_music_id']
    if amid in spotify_mapping.index:
        return spotify_mapping.loc[amid, 'spotify_id']
    else:
        spotify_id = find_spotify_id_for_artist_name(sp, song['artist'], song['name'], spotify_mapping)
        spotify_mapping.loc[amid] = {'spotify_id': spotify_id}
        spotify_mapping.to_csv(DATA_DIR / "spotify-mapping.csv", index_label='apple_music_id')
        return spotify_id


def main() -> None:
    sp = get_sp()
    spotify_mapping = pd.read_csv(DATA_DIR / "spotify-mapping.csv").set_index('apple_music_id')

    playlist_id = '74eUXrePcNpIrEYaFBlmbw'
    results = sp.playlist_items(playlist_id)

    tracks = results['items']
    while results['next']:
        results = sp.next(results)
        tracks.extend(results['items'])

    df = pd.read_csv(DATA_DIR / "songs-would-play.csv")

    for i, song in df.iterrows():
        spotify_id = find_spotify_id_for_song(sp, song, spotify_mapping)
        if spotify_id == '-1':
            print(f"No spotify ID for {song['artist']} - {song['name']}")
        elif any(track['track']['id'] == spotify_id for track in tracks):
            print(f"Already in the playlist {song['artist']} - {song['name']}")
            continue
        else:
            print(f"Adding {song['artist']} - {song['name']}")
            sp.playlist_add_items(playlist_id, [f"spotify:track:{spotify_id}"])


if __name__ == "__main__":
    main()
