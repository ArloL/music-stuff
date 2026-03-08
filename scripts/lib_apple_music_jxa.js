function hexIdToInt(hexId) {
    try {
        const value = BigInt(`0x${hexId}`);
        return value >= (1n << 63n) ? value - (1n << 64n) : value;
    } catch {
        return null;
    }
}

function intToHexId(idStr) {
    let value = BigInt(idStr);
    if (value < 0n) value += (1n << 64n);
    return value.toString(16).toUpperCase().padStart(16, '0');
}

function _mapTrackProperties(trackProperties) {
    return {
        ...trackProperties,
        persistentID: hexIdToInt(trackProperties.persistentID).toString(),
        location: trackProperties.location.toString(),
    }
}

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
            if (seen.has(track.persistentID)) continue;
            seen.add(track.persistentID);
            result.push(_mapTrackProperties(track));
        }
    }
    return result;
}

function findTracksByPlaylistName(playlistName) {
    return findPlaylistByName(playlistName)
        .self
        .tracks
        .properties()
        .map(_mapTrackProperties);
}

function findTrackById(idStr) {
    const hexId = intToHexId(idStr);
    const music = Application("Music");
    const tracks = music.libraryPlaylists[0].tracks.whose({ persistentID: { _equals: hexId } });
    if (tracks.length === 0) return null;
    return _mapTrackProperties(tracks[0].properties());
}

function findAllTracks() {
    const music = Application("Music");
    return music
        .libraryPlaylists[0]
        .tracks
        .properties()
        .map(_mapTrackProperties);
}
