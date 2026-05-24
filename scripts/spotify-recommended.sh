#!/bin/sh

set -o errexit
set -o nounset
set -o xtrace

uv run spotify-browser-add-to-playlist \
    --headless \
    --recommendations 50 \
    "Recommended" "Candidates"

uv run spotify-browser-add-to-playlist \
    --headless \
    --recommendations 50 \
    "Recommended" "Would Play"
