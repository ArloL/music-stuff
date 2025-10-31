import spotipy
import json
import requests
import csv
from urllib.parse import urlparse
from spotify import get_sp, user_playlist_by_name, all_playlist_items

def main(target_playlist_name, source_playlist_name):
    sp = get_sp()

    target_playlist = user_playlist_by_name(sp, target_playlist_name)

    source_playlist = user_playlist_by_name(sp, source_playlist_name)

    tracks = all_playlist_items(sp, source_playlist['id'])

    for i in range(0, len(tracks), 100):
        sp.playlist_add_items(
            target_playlist['id'],
            [t['track']['id'] for t in tracks[i:i+100]]
        )

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Add all tracks from one playlist to another')
    parser.add_argument('target_playlist_name', nargs='?', default='Recommended', help='The playlist which will have songs added')
    parser.add_argument('source_playlist_name', nargs='?', default="Gerd Janson's track IDs", help='The playlist which indicates the songs that should be removed')

    args = parser.parse_args()
    main(args.target_playlist_name, args.source_playlist_name)
