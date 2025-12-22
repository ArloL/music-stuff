import spotipy
from spotipy.oauth2 import SpotifyOAuth

def get_sp():
    return spotipy.Spotify(auth_manager=SpotifyOAuth(client_id='567ed2100ef746ff8bc4765c6fe21ac3',
                                                client_secret='',
                                                redirect_uri='http://127.0.0.1:50872',
                                                scope='user-library-modify,playlist-read-private,playlist-modify-private,playlist-modify-public'))

def all_items(sp, results):
    items = results['items']
    while results['next']:
        results = sp.next(results)
        items.extend(results['items'])
    return items

def user_playlist_by_name(sp, playlist_name):
    playlists = all_items(sp, sp.current_user_playlists())
    for playlist in playlists:
        if playlist['name'] == playlist_name:
            return playlist
    raise ValueError(f'No playlist with name {playlist_name}')

def all_playlist_items(sp, playlist_id):
    return all_items(sp, sp.playlist_items(playlist_id))
