#!/bin/sh

set -o errexit
set -o nounset
set -o xtrace

ReleaseRadar="id:37i9dQZEVXbr5m74MUAgNM"
DiscoverWeekly="id:37i9dQZEVXcJUQATtKZVAY"

uv run spotify-browser-add-to-playlist --headless \
    "Recommended" \
    "${ReleaseRadar}" \
    "${DiscoverWeekly}"
