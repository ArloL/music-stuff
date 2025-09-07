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
