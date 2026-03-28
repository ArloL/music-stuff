#!/bin/sh

set -o errexit
set -o nounset
set -o xtrace

uv run playlist-csv "Critical Mass 2025-01"
uv run playlist-csv "Critical Mass 2025-03"
uv run playlist-csv "Critical Mass 2025-05"
uv run playlist-csv "Critical Mass 2025-06"
uv run playlist-csv "Critical Mass 2025-07"
uv run playlist-csv "Critical Mass 2025-08"
uv run playlist-csv "Critical Mass 2025-09"
uv run playlist-csv "Critical Mass 2026-03"
uv run playlist-csv "Critical Mass Next"
uv run playlist-csv "Would Play"
uv run playlist-csv "Would Play And Didnt"
