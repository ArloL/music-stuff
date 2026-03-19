import pandas as pd
from pathlib import Path
from music_stuff.lib.lib_spotify import get_sp, all_playlist_items

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
        spotify_mapping.to_csv(DATA_DIR / "spotify-mapping.csv", index_label='apple_music_id', lineterminator='\n')
        return spotify_id


def main() -> None:
    sp = get_sp()
    spotify_mapping = pd.read_csv(DATA_DIR / "spotify-mapping.csv").set_index('apple_music_id')

    playlist_id = '74eUXrePcNpIrEYaFBlmbw'
    tracks = all_playlist_items(sp, playlist_id)

    df = pd.read_csv(DATA_DIR / "songs-would-play.csv")

    existing_ids = {track['item']['id'] for track in tracks if track.get('item')}
    to_add = []
    for i, song in df.iterrows():
        spotify_id = find_spotify_id_for_song(sp, song, spotify_mapping)
        if spotify_id == '-1':
            print(f"No spotify ID for {song['artist']} - {song['name']}")
        elif spotify_id in existing_ids:
            print(f"Already in the playlist {song['artist']} - {song['name']}")
        else:
            print(f"Adding {song['artist']} - {song['name']}")
            to_add.append(f"spotify:track:{spotify_id}")

    for i in range(0, len(to_add), 100):
        sp.playlist_add_items(playlist_id, to_add[i:i+100])


if __name__ == "__main__":
    main()
