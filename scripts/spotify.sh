#!/bin/sh

set -o errexit
set -o nounset
set -o xtrace

uv run spotify-playlist-delete-duplicates "Would Play"
uv run spotify-playlist-delete-duplicates Recommended
uv run spotify-playlist-delete-present-in-other-playlist Recommended "Would Play"
uv run spotify-playlist-delete-present-in-other-playlist Recommended Listened
