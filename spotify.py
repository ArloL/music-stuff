import spotipy
import json
import requests
import csv
from spotipy.oauth2 import SpotifyOAuth

def get_audio_features(track_id):
    response = requests.request(
        'GET',
        'https://api.reccobeats.com/v1/audio-features',
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
        'spotify_id': track_id,
        'id': '-1',
        'acousticness': -1,
        'danceability': -1,
        'energy': -1,
        'instrumentalness': -1,
        'key': -1,
        'liveness': -1,
        'loudness': -1,
        'mode': -1,
        'speechiness': -1,
        'tempo': -1,
        'valence': -1
    }

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id='567ed2100ef746ff8bc4765c6fe21ac3',
                                               client_secret='9c2182d252b048bdb09ec8307842b455',
                                               redirect_uri='http://127.0.0.1:50872',
                                               scope='user-library-read'))

# print(json.dumps(track, indent=1))

critical_mass_selection = '74eUXrePcNpIrEYaFBlmbw'
critical_mass_2025_08 = '6LOmsXgiO9FHvRKnlwbwxg'
results = sp.playlist_items(critical_mass_selection)

tracks = results['items']
while results['next']:
    results = sp.next(results)
    tracks.extend(results['items'])

spotify_to_beatunes_key_map = {
    (-1, -1): -1, # no key detected
    (0, 1): 10, # ??: ??
    (0, 2): 24, # 7A: Pavla, Noura - Don't Owe Me a Thing
    (0, 3): 14, # 2A: ??
    (0, 4): 4, # 9A: DAMH - Black Night
    (0, 5): 18, # 4A: Jamie xx - Sleep Sound
    (0, 6): 8, # 11A: Youandewan - 1988 - Original Mix
    (0, 7): 22, # 6A: Guy Gerber, &ME - What To Do - &ME Remix
    (0, 8): 12, # ??: ??
    (0, 9): 2, # 8A: Dorisburg - Emotion - Original
    (0, 10): 16, # 3A: Leon Vynehall - Butterflies
    (0, 11): 6, # 10A: Robag Wruhme als Die Dub Rolle - Lampetee
    (1, 0): 1, # 8B: Axel Boman - Purple Drank
    (1, 1): 15, # 3B: Todd Terje - Ragysh
    (1, 2): 5, # 10B: Daniel Bortz - Wohin Willst Du?
    (1, 3): 19, # ??: ??
    (1, 4): 9, # ??: ??
    (1, 5): 23, # ??: Albion, Oliver Lieb - Air - Oliver Lieb Remix
    (1, 6): 13, # 2B: Luvless - Luvmaschine
    (1, 7): 3, # ??: DJ Koze - I Want To Sleep
    (1, 8): 17, # 4B: DJ Seinfeld - U
    (1, 9): 7, # ??: Map.ache - Thank U Again
    (1, 10): 21, # ??: Jeigo - Pearl Leaf
    (1, 11): 11, # ??: ??
}

with open('songs_spotify.csv', 'w', newline='') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow([
        'song_id',
        'key',
        'bpm',
        'id',
        'spotify_id',
        'acousticness',
        'danceability',
        'energy',
        'instrumentalness',
        'key',
        'liveness',
        'loudness',
        'mode',
        'speechiness',
        'valence'])

    for track in tracks:
        track_details = track['track']
        features = get_audio_features(track_details['id'])
        writer.writerow([
            f'{', '.join([d['name'] for d in track_details['artists']])} - {track_details['name']}',
            spotify_to_beatunes_key_map[(features['mode'], features['key'])],
            features['tempo'],
            features['id'],
            features['spotify_id'],
            features['acousticness'],
            features['danceability'],
            features['energy'],
            features['instrumentalness'],
            features['key'],
            features['liveness'],
            features['loudness'],
            features['mode'],
            features['speechiness'],
            features['valence']
        ])
