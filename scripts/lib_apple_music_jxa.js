function findPlaylists() {
    return Application("Music").playlists.properties();
}

function findPlaylistByName(name) {
    return Application("Music").playlists.whose({ name: { _equals: name } })[0];
}

function findTracksByFolder(folderName) {
    const music = Application("Music");
    const folderID = findPlaylistByName(folderName).id();
    const seen = new Set();
    const result = [];
    for (const pl of music.playlists()) {
        if (!pl.parent || pl.parent().id() !== folderID) continue;
        for (const p of pl.tracks.properties()) {
            if (seen.has(p.id)) continue;
            seen.add(p.id);
            result.push(p);
        }
    }
    return result;
}

function findTracksByPlaylist(playlistName) {
    return findPlaylistByName(playlistName).tracks.properties();
}

function findAllTracks() {
    return Application("Music").libraryPlaylists[0].tracks.properties();
}
