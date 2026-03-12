#!/usr/bin/env python3
"""
Export an Apple Music playlist to CSV with BPM and key data.

Usage:
    uv run python playlist-csv.py "Critical Mass 2025-08"
"""
import argparse
import csv
import re
from pathlib import Path

from music_stuff.lib.lib_apple_music import find_songs_by_playlist_name

OUTPUT_DIR = Path(__file__).parent.parent.parent / "data"
FIELDNAMES = ["apple_music_id", "artist", "name", "key", "bpm"]


def _playlist_name_to_filename(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"songs-{slug}.csv"


def write_playlist_to_file(playlist_name: str) -> None:
    filename = _playlist_name_to_filename(playlist_name)
    print(f"Writing '{playlist_name}' → {filename} ...")
    songs = find_songs_by_playlist_name(playlist_name)
    output = OUTPUT_DIR / filename
    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for s in songs:
            writer.writerow({
                "apple_music_id": s.persistentID,
                "artist": s.artist,
                "name": s.name,
                "key": s.comment or "",
                "bpm": s.bpm or "",
            })
    print(f"  Wrote {len(songs)} songs to {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export an Apple Music playlist to CSV.")
    parser.add_argument("playlist", nargs="+", help="Name(s) of Apple Music playlist(s) to export")
    args = parser.parse_args()

    for name in args.playlist:
        write_playlist_to_file(name)


if __name__ == "__main__":
    main()
