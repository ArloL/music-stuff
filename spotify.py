import spotipy
import json
import requests
import csv
from spotipy.oauth2 import SpotifyOAuth

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id="567ed2100ef746ff8bc4765c6fe21ac3",
                                               client_secret="9c2182d252b048bdb09ec8307842b455",
                                               redirect_uri="http://127.0.0.1:50872",
                                               scope="user-library-read"))

# print(json.dumps(track, indent=1))

results = sp.playlist_items('74eUXrePcNpIrEYaFBlmbw')

tracks = results['items']
while results['next']:
    results = sp.next(results)
    tracks.extend(results['items'])

track_ids = []

for track in tracks:
    #print(f"{json.dumps(track['track'], indent=1)}")
    track_ids.append(track['track']['id'])
    artists = []
    for artist in track['track']['artists']:
        artists.append(artist['name'])
    track['track']['artist_names'] = ', '.join(artists)

response = requests.request(
    "GET",
    "https://api.reccobeats.com/v1/audio-features",
    headers={
        'Accept': 'application/json'
    },
    params={
        'ids': track_ids
    })

with open('songs_spotify.csv', 'w', newline='') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['song_id', 'key', 'bpm'])
    for index, features in enumerate(json.loads(response.text)['content']):
        writer.writerow([tracks[index]['track']['artist_names'] + " - " + tracks[index]['track']['name'], features['key'], features['tempo']])
