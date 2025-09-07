import spotipy
import json
import requests
import csv
from urllib.parse import urlparse
from spotipy.oauth2 import SpotifyOAuth

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id='567ed2100ef746ff8bc4765c6fe21ac3',
                                               client_secret='9c2182d252b048bdb09ec8307842b455',
                                               redirect_uri='http://127.0.0.1:50872',
                                               scope='user-library-read,playlist-modify-public'))

# print(json.dumps(track, indent=1))

playlist_id = '74eUXrePcNpIrEYaFBlmbw'
results = sp.playlist_items(playlist_id)

tracks = results['items']
while results['next']:
    results = sp.next(results)
    tracks.extend(results['items'])

track_ids = set()
items = [ { "uri":"4iV5W9uYEdYUVa79Axb7Rh", "positions":[2] }, { "uri":"1301WleyT98MSxVHPZCA6M", "positions":[7] } ]

for i, track in enumerate(tracks):
    track_id = track['track']['id']
    if (track_id in track_ids):
        print(f'{i} {track_id}')
        sp.playlist_remove_specific_occurrences_of_items(playlist_id, [{'uri':track_id, 'positions':[i]}])
    track_ids.add(track_id)

