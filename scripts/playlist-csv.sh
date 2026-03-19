#!/bin/sh

set -o errexit
set -o nounset
set -o xtrace

uv run playlist-csv "Critical Mass 2025-08"
uv run playlist-csv "Critical Mass Next"
uv run playlist-csv "Would Play"
uv run playlist-csv "Would Play And Didnt"
