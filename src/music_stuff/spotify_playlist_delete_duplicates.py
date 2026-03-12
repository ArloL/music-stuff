import spotipy
import json
import requests
import csv
from urllib.parse import urlparse
from music_stuff.lib.lib_spotify import get_sp, user_playlist_by_name, all_playlist_items

def main(playlist_name):
    sp = get_sp()

    playlist = user_playlist_by_name(sp, playlist_name)

    tracks = all_playlist_items(sp, playlist['id'])

    track_ids = {}

    position = 0
    for track in tracks:
        track_id = track['item']['id']
        if track_id in track_ids:
            print(f'Removing {position} {track_id}')
            sp.playlist_remove_all_occurrences_of_items(playlist['id'], [track_id])
            sp.playlist_add_items(playlist['id'], [track_id], position=track_ids[track_id])
        else:
            track_ids[track_id] = position
            position += 1

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Delete duplicates from a Spotify playlist')
    parser.add_argument('playlist_name', nargs='?', default='Would Play', help='Name of the playlist')

    args = parser.parse_args()
    main(args.playlist_name)
