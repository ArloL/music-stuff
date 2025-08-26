import spotipy
from spotipy.oauth2 import SpotifyOAuth

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id="567ed2100ef746ff8bc4765c6fe21ac3",
                                               client_secret="9c2182d252b048bdb09ec8307842b455",
                                               redirect_uri="http://127.0.0.1:50872",
                                               scope="user-library-read"))


taylor_uri = 'spotify:artist:06HL4z0CvFAxyc27GXpf02'

results = sp.artist_albums(taylor_uri, album_type='album')
albums = results['items']
while results['next']:
    results = sp.next(results)
    albums.extend(results['items'])

for album in albums:
    print(album['name'])

