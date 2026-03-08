function _mapPlaylist(playlist) {
    var parent = null;
    var parents = [];
    try {
        parent = _mapPlaylist(playlist.parent());
        parents = [parent, ...parent.parents];
    } catch (e) {
        // ignore
    }
    return {
        parent,
        parents,
        self: playlist,
        ...playlist.properties(),
    };
}

function findPlaylists() {
    const music = Application("Music");
    return music.playlists().map(_mapPlaylist);
}

function findPlaylistByName(name) {
    const music = Application("Music");
    const playlists = music.playlists.whose({ name: { _equals: name } });
    if (playlists.length > 1) {
        throw new Error("More than one playlist named " + name);
    }
    return _mapPlaylist(playlists[0]);
}

function findPlaylistsByFolderName(folderName) {
    const folder = findPlaylistByName(folderName);
    return findPlaylists()
        .filter((playlist) => {
            return playlist.parents.some((parent) => parent.id === folder.id);
        });
}

function findTracksByFolderName(folderName) {
    const seen = new Set();
    const result = [];
    const playlists = findPlaylistsByFolderName(folderName);
    for (const playlist of playlists) {
        for (const track of playlist.self.tracks.properties()) {
            if (seen.has(track.id)) continue;
            seen.add(track.id);
            result.push(track);
        }
    }
    return result;
}

function findTracksByPlaylistName(playlistName) {
    return findPlaylistByName(playlistName).self.tracks.properties();
}

function findAllTracks() {
    const music = Application("Music");
    return music.libraryPlaylists[0].tracks.properties();
}
