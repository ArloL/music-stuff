#!/bin/sh

set -o errexit
set -o nounset
set -o xtrace

uv run spotify-browser-track-radio-to-playlist \
    --headless \
    "Recommended Radio" "Would Play"
