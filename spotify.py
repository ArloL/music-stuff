import spotipy
import json
import requests
import csv
from spotipy.oauth2 import SpotifyOAuth

def get_audio_features(track_id):
    response = requests.request(
        "GET",
        "https://api.reccobeats.com/v1/audio-features",
        headers={
            'Accept': 'application/json'
        },
        params={
            'ids': track_id
        })
    json_response = json.loads(response.text)
    content = json_response['content']
    if len(content) > 0:
        content[0]['spotify_id'] = track_id
        return content[0]
    return {
        'spotify_id': track_id
    }

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

with open('songs_spotify.csv', 'w', newline='') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['song_id', 'key', 'bpm'])
    for track in tracks:
        track_details = track['track']
        features = get_audio_features(track_details['id'])
        artists = []
        for artist in track_details['artists']:
            artists.append(artist['name'])
        writer.writerow([', '.join(artists) + " - " + track_details['name'], features['key'], features['tempo']])
