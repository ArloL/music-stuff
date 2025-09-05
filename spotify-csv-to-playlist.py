import spotipy
import json
import requests
import pandas as pd
from urllib.parse import urlparse
from spotipy.oauth2 import SpotifyOAuth

def find_spotify_id_for_artist_name(artist, name):
    query = f"{artist} {name}"
    results = sp.search(query)
    tracks = results['tracks']['items']
    #for i, track in enumerate(tracks):
    #    print(f"{track}")
    #     print(f'{', '.join([d['name'] for d in track['artists']])} - {track['name']}')
    return tracks[0]['id']


def find_spotify_id_for_song(spotify_mapping, song):
    row = spotify_mapping.loc[spotify_mapping['apple_music_id'].astype(str) == song['apple_music_id'], 'spotify_id']
    if row.empty:
        spotify_id = find_spotify_id_for_artist_name(song['artist'], song['name'])
        spotify_mapping.loc[len(spotify_mapping)] = {'apple_music_id': song['apple_music_id'], 'spotify_id': spotify_id}
        spotify_mapping.to_csv("spotify-mapping.csv", index=False)
        return spotify_id
    return row.astype(str).iloc[0]

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id='567ed2100ef746ff8bc4765c6fe21ac3',
                                               client_secret='9c2182d252b048bdb09ec8307842b455',
                                               redirect_uri='http://127.0.0.1:50872',
                                               scope='user-library-read,playlist-modify-private'))

playlist_id = '74eUXrePcNpIrEYaFBlmbw'
results = sp.playlist_items(playlist_id)

tracks = results['items']
while results['next']:
    results = sp.next(results)
    tracks.extend(results['items'])

spotify_mapping = pd.read_csv("spotify-mapping.csv")

df = pd.read_csv("songs.csv")

for i, song in df.iterrows():
    spotify_id = find_spotify_id_for_song(spotify_mapping, song)
    print(f"{song['artist']}, {spotify_id}")
    if not any(track['track']['id'] == spotify_id for track in tracks):
        print("nope")
        #sp.playlist_add_items(playlist_id, [f"spotify:track:{spotify_id}"])
