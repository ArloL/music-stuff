import json
import requests
import pandas as pd
from urllib.parse import urlparse
from lib_spotify import get_sp

sp = get_sp()
spotify_mapping = pd.read_csv("spotify-mapping.csv").set_index('apple_music_id')

def find_spotify_id_for_artist_name(artist, name):
    query = f"{artist} {name}"
    results = sp.search(query)
    tracks = results['tracks']['items']
    return tracks[0]['id']

def find_spotify_id_for_song(song):
    amid = song['apple_music_id']
    if amid in spotify_mapping.index:
        return spotify_mapping.loc[amid, 'spotify_id']
    else:
        spotify_id = find_spotify_id_for_artist_name(song['artist'], song['name'])
        spotify_mapping.loc[amid] = {'spotify_id': spotify_id}
        spotify_mapping.to_csv("spotify-mapping.csv", index_label='apple_music_id')
        return spotify_id

playlist_id = '74eUXrePcNpIrEYaFBlmbw'
results = sp.playlist_items(playlist_id)

tracks = results['items']
while results['next']:
    results = sp.next(results)
    tracks.extend(results['items'])

df = pd.read_csv("songs-would-play.csv")

for i, song in df.iterrows():
    spotify_id = find_spotify_id_for_song(song)
    if spotify_id == '-1':
        print(f"No spotify ID for {song['artist']} - {song['name']}")
    elif any(track['track']['id'] == spotify_id for track in tracks):
        print(f"Already in the playlist {song['artist']} - {song['name']}")
        continue
    else:
        print(f"Adding {song['artist']} - {song['name']}")
        sp.playlist_add_items(playlist_id, [f"spotify:track:{spotify_id}"])
