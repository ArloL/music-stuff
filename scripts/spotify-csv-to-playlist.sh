#!/bin/sh

set -o errexit
set -o nounset
set -o xtrace

cd "$(dirname "$0")/.." || exit 1

uv run spotify-csv-to-playlist "$@" \
    data/songs-critical-mass-2025-01.csv "Critical Mass 2025-01"
uv run spotify-csv-to-playlist "$@" \
    data/songs-critical-mass-2025-03.csv "Critical Mass 2025-03"
uv run spotify-csv-to-playlist "$@" \
    data/songs-critical-mass-2025-05.csv "Critical Mass 2025-05"
uv run spotify-csv-to-playlist "$@" \
    data/songs-critical-mass-2025-06.csv "Critical Mass 2025-06"
uv run spotify-csv-to-playlist "$@" \
    data/songs-critical-mass-2025-07.csv "Critical Mass 2025-07"
uv run spotify-csv-to-playlist "$@" \
    data/songs-critical-mass-2025-08.csv "Critical Mass 2025-08"
uv run spotify-csv-to-playlist "$@" \
    data/songs-critical-mass-2025-09.csv "Critical Mass 2025-09"
uv run spotify-csv-to-playlist "$@" \
    data/songs-critical-mass-2026-03.csv "Critical Mass 2026-03"
uv run spotify-csv-to-playlist "$@" \
    data/songs-critical-mass-2026-05.csv "Critical Mass 2026-05"
uv run spotify-csv-to-playlist "$@" \
    data/songs-critical-mass-2026-06.csv "Critical Mass 2026-06"
uv run spotify-csv-to-playlist "$@" \
    data/songs-critical-mass-2026-07.csv "Critical Mass 2026-07"
uv run spotify-csv-to-playlist "$@" \
    data/songs-critical-mass-2026-08.csv "Critical Mass 2026-08"
uv run spotify-csv-to-playlist "$@" \
    data/songs-critical-mass-2026-10.csv "Critical Mass 2026-10"
uv run spotify-csv-to-playlist "$@" \
    data/songs-would-play.csv "Would Play"
