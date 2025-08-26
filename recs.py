import json
import requests

try:
    import http.client as http_client
except ImportError:
    # Python 2
    import httplib as http_client
#http_client.HTTPConnection.debuglevel = 1

def get_audio_features(spotify_id):
    response = requests.request(
        'GET',
        f'https://api.reccobeats.com/v1/track/{spotify_id}/audio-features',
        headers={
            'Accept': 'application/json'
        })
    return json.loads(response.text)

def get_recommendation(spotify_or_reccobeats_id):
    response = requests.request(
        'GET',
        'https://api.reccobeats.com/v1/track/recommendation',
        headers={
            'Accept': 'application/json'
        },
        params={
            'size': 5,
            'seeds': [spotify_or_reccobeats_id],
        })
    return json.loads(response.text)['content']


def get_reccobeats_id(spotify_id):
    response = requests.request(
        'GET',
        'https://api.reccobeats.com/v1/audio-features',
        headers={
            'Accept': 'application/json'
        },
        params={
            'ids': spotify_id
        })
    return json.loads(response.text)['content'][0]['id']

def get_track_detail(reccobeats_id):
    response = requests.request(
        'GET',
        f'https://api.reccobeats.com/v1/track/{reccobeats_id}',
        headers={
            'Accept': 'application/json'
        })
    return json.loads(response.text)

cant_see_what_is_burning_there = '4LTt3LIHKYhD2D1Mgfg2s1'
peace_u_need = '4A8tKYA7gwZzQ4jVwIv1sv'
track_detail = get_track_detail(get_reccobeats_id(cant_see_what_is_burning_there))
rec = get_recommendation(track_detail['id'])
#print(json.dumps(rec, indent=1))
for track in rec:
    track['audio_features'] = get_audio_features(track['id'])
    print(f'{', '.join([d['name'] for d in track['artists']])} - {track['trackTitle']}: {track['href']}')
