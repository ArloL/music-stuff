#!/usr/bin/env python3
"""
Extend data/spotify-mapping.csv by searching Spotify for tracks that don't yet
have a mapping.

Usage:
    uv run spotify-mapping-fill [--folder NAME | --playlist NAME]

Defaults to --playlist "Would Play". For each Apple Music song in the selected
scope that is missing from spotify-mapping.csv, searches Spotify by
"<artist> <name>" and appends a row. Misses are recorded as spotify_id="-1"
so they aren't retried on future runs.
"""

import argparse
import csv
from pathlib import Path

from music_stuff.lib.lib_apple_music import (
    find_songs_by_folder_name,
    find_songs_by_playlist_name,
)
from music_stuff.lib.lib_spotify import get_sp

SPOTIFY_MAPPING_PATH = (
    Path(__file__).parent.parent.parent / "data" / "spotify-mapping.csv"
)


def _load_mapping() -> dict[str, str]:
    if not SPOTIFY_MAPPING_PATH.exists():
        return {}
    with open(SPOTIFY_MAPPING_PATH, newline="", encoding="utf-8") as f:
        return {row["apple_music_id"]: row["spotify_id"] for row in csv.DictReader(f)}


def _write_mapping(mapping: dict[str, str]) -> None:
    with open(SPOTIFY_MAPPING_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["apple_music_id", "spotify_id"])
        for amid, sid in mapping.items():
            writer.writerow([amid, sid])


def _search_spotify_id(sp, artist: str, name: str) -> str:
    query = f"{artist} {name}".strip()
    if not query:
        return "-1"
    results = sp.search(query)
    tracks = results.get("tracks", {}).get("items", [])
    if not tracks:
        return "-1"
    return tracks[0]["id"]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fill in missing entries in data/spotify-mapping.csv."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--folder", metavar="NAME", help="Songs in this Music library folder"
    )
    group.add_argument(
        "--playlist",
        metavar="NAME",
        default="Would Play",
        help="Songs in this Music library playlist (default: Would Play)",
    )
    args = parser.parse_args()

    if args.folder:
        desc = f"folder '{args.folder}'"
        songs = find_songs_by_folder_name(args.folder)
    else:
        desc = f"playlist '{args.playlist}'"
        songs = find_songs_by_playlist_name(args.playlist)
    print(f"Loaded {len(songs)} songs from {desc}.")

    mapping = _load_mapping()
    missing = [s for s in songs if s.id not in mapping]
    print(f"{len(missing)} song(s) missing from spotify-mapping.csv.")
    if not missing:
        return

    sp = get_sp()
    added = 0
    misses = 0
    for i, song in enumerate(missing, 1):
        spotify_id = _search_spotify_id(sp, song.artist, song.name)
        mapping[song.id] = spotify_id
        if spotify_id == "-1":
            misses += 1
            print(f"  [{i}/{len(missing)}] miss: {song.artist} - {song.name}")
        else:
            added += 1
            print(f"  [{i}/{len(missing)}] {song.artist} - {song.name} -> {spotify_id}")
        _write_mapping(mapping)

    print(f"Added {added} mapping(s), recorded {misses} miss(es).")


if __name__ == "__main__":
    main()
