#!/bin/sh

set -o errexit
set -o nounset
set -o xtrace

#uv run python spotify-playlist-add-from-other-playlist.py Recommended 'Played by Jamie xx'
uv run python spotify-playlist-add-from-other-playlist.py Recommended "Gerd Janson's track IDs"
#uv run python spotify-playlist-delete-duplicates.py 'Recommended'
#uv run python spotify-playlist-delete-present-in-other-playlist.py Recommended Listened
#
