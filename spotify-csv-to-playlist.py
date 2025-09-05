import spotipy
import json
import requests
import pandas as pd
from urllib.parse import urlparse
from spotipy.oauth2 import SpotifyOAuth

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id='567ed2100ef746ff8bc4765c6fe21ac3',
                                               client_secret='9c2182d252b048bdb09ec8307842b455',
                                               redirect_uri='http://127.0.0.1:50872',
                                               scope='user-library-read'))

# print(json.dumps(track, indent=1))

playlist_id = '74eUXrePcNpIrEYaFBlmbw'

df = pd.read_csv("songs.csv")
