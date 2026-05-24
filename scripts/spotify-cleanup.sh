#!/bin/sh

set -o errexit
set -o nounset
set -o xtrace

uv run spotify-playlist-delete-present-in-other-playlist \
    "Recommended Radio" Listened

uv run spotify-playlist-delete-duplicates \
    "Recommended Radio"

uv run spotify-playlist-delete-present-in-other-playlist \
    Recommended Listened

uv run spotify-playlist-delete-duplicates \
    Recommended

uv run spotify-playlist-delete-present-in-other-playlist \
    "Recommended" "Recommended Radio"
