import csv
from music_stuff.lib.lib_spotify import get_sp, all_playlist_items
from music_stuff.lib.lib_reccobeats import get_audio_features, spotify_key_to_open_key


def main() -> None:
    sp = get_sp()

    # print(json.dumps(track, indent=1))

    critical_mass_selection = '74eUXrePcNpIrEYaFBlmbw'
    tracks = all_playlist_items(sp, critical_mass_selection)

    with open('songs_spotify.csv', 'w', newline='') as csvfile:
        writer = csv.writer(csvfile, lineterminator='\n')
        writer.writerow([
            'apple_music_id',
            'key',
            'bpm',
            'id',
            'spotify_id',
            'acousticness',
            'danceability',
            'energy',
            'instrumentalness',
            'spotify_key',
            'liveness',
            'loudness',
            'mode',
            'speechiness',
            'valence'])

        spotify_ids = [t['item']['id'] for t in tracks]
        features_dict = get_audio_features(spotify_ids)
        features = [features_dict[sid] for sid in spotify_ids if sid in features_dict]
        for i, track in enumerate(tracks):
            track_details = track['item']
            artist_names = ', '.join(d['name'] for d in track_details['artists'])
            writer.writerow([
                f'{artist_names} - {track_details["name"]}',
                spotify_key_to_open_key(int(features[i]['mode']), int(features[i]['key'])),
                features[i]['tempo'],
                features[i]['id'],
                features[i]['spotify_id'],
                features[i]['acousticness'],
                features[i]['danceability'],
                features[i]['energy'],
                features[i]['instrumentalness'],
                features[i]['key'],
                features[i]['liveness'],
                features[i]['loudness'],
                features[i]['mode'],
                features[i]['speechiness'],
                features[i]['valence']
            ])


if __name__ == "__main__":
    main()
