import spotipy
import json
import requests
import csv
from urllib.parse import urlparse
from spotify import get_sp, user_playlist_by_name, all_playlist_items

def main(playlist_name):
    sp = get_sp()

    playlist = user_playlist_by_name(sp, playlist_name)

    tracks = all_playlist_items(sp, playlist['id'])

    track_ids = set()

    items_to_delete = set()

    for i, track in enumerate(tracks):
        track_id = track['track']['id']
        if (track_id in track_ids):
            print(f'Removing {i} {track_id}')
            items_to_delete.add(track_id)
        track_ids.add(track_id)

    if len(items_to_delete) > 0:
        sp.playlist_remove_all_occurrences_of_items(playlist['id'], items_to_delete)
        sp.playlist_add_items(playlist['id'], items_to_delete)

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Delete duplicates from a Spotify playlist')
    parser.add_argument('playlist_name', nargs='?', default='Would Play', help='Name of the playlist')

    args = parser.parse_args()
    main(args.playlist_name)
