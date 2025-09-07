import spotipy
import json
import requests
import csv
from urllib.parse import urlparse
from spotipy.oauth2 import SpotifyOAuth

def main(playlist_name):
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id='567ed2100ef746ff8bc4765c6fe21ac3',
                                                client_secret='9c2182d252b048bdb09ec8307842b455',
                                                redirect_uri='http://127.0.0.1:50872',
                                                scope='user-library-read,playlist-modify-public'))

    # print(json.dumps(track, indent=1))

    results = sp.current_user_playlists()
    playlists = results['items']
    while results['next']:
        results = sp.next(results)
        playlists.extend(results['items'])

    playlist_id = -1
    for playlist in playlists:
        if playlist['name'] == playlist_name:
            playlist_id = playlist['id']
    if playlist_id == -1:
        raise ValueError(f'No playlist with name {playlist_name}')

    results = sp.playlist_items(playlist_id)
    tracks = results['items']
    while results['next']:
        results = sp.next(results)
        tracks.extend(results['items'])

    track_ids = set()

    for i, track in enumerate(tracks):
        track_id = track['track']['id']
        if (track_id in track_ids):
            print(f'Removing {i} {track_id}')
            sp.playlist_remove_specific_occurrences_of_items(playlist_id, [{'uri':track_id, 'positions':[i]}])
        track_ids.add(track_id)

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Delete duplicates from a Spotify playlist')
    parser.add_argument('playlist_name', nargs='?', default='Would Play', help='Name of the playlist')

    args = parser.parse_args()
    main(args.playlist_name)
