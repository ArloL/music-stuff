#!/usr/bin/env python3
"""
Extract analyzed BPM data from djay's MediaLibrary.db and merge with
comments and BPM from the Apple Music library via osascript.

Usage:
    uv run python extract_bpm.py [--folder NAME]

Options:
    --folder NAME   Filter to tracks in a Music library folder (e.g. "Critical Mass")

Database structure:
- `database2` holds all data as binary TSAF blobs
- `secondaryIndex_mediaItemAnalyzedDataIndex` holds indexed BPM values
- All collections share a common hash key per track

TSAF blob format: strings are stored as 0x08 <null-terminated UTF-8 string>
Fields are stored value-first, then key (e.g. "Only Love", "title").

Cross-reference key:
  djay apple_id  "com.apple.iTunes:<decimal>"
  osascript Persistent ID  "<HEX>"
  These represent the same value in different bases.
"""

import csv
import re
import sys
import argparse
from pathlib import Path

from lib_apple_music import find_tracks_by_folder_name, find_all_tracks
from lib_djay import load_djay_index
from lib_essentia import analyse, consensus_key

OUTPUT_PATH = Path(__file__).parent / "songs-djay-diff.csv"


_KEY_PAT = re.compile(r"Key\s+(\d+)([dm])", re.IGNORECASE)


def _parse_open_key(s: str) -> tuple[int, str] | None:
    m = _KEY_PAT.fullmatch(s.strip()) if s else None
    return (int(m.group(1)), m.group(2).lower()) if m else None


def _key_diff(djay_key: str, essentia_key: str, comment_key: str) -> str:
    """
    Return the sum of absolute pairwise circular distances among open_key,
    essentia_key, and comment as a plain integer string.
    - All three agree → 0
    - Two agree, one differs by d → 2d
    - All three disagree → d12 + d13 + d23 (scores higher than two-agree for same spread)
    Returns "" if fewer than two keys are present.
    """
    available = [v for v in (_parse_open_key(k) for k in (djay_key, essentia_key, comment_key)) if v is not None]
    if len(available) < 2:
        return ""

    total = 0
    for i in range(len(available)):
        for j in range(i + 1, len(available)):
            n1, n2 = available[i][0], available[j][0]
            diff = (n2 - n1) % 12
            if diff > 6:
                diff -= 12
            total += abs(diff)
    return str(total)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Export djay BPM data merged with Apple Music metadata.")
    parser.add_argument("--folder", metavar="NAME", help="Filter to tracks in this Music library folder")
    args = parser.parse_args()

    # --- Load Music metadata ---
    desc = f"folder '{args.folder}'" if args.folder else "all tracks"
    print(f"Loading Apple Music metadata for {desc}...")
    tracks = find_tracks_by_folder_name(args.folder) if args.folder else find_all_tracks()
    print(f"  Loaded metadata for {len(tracks)} tracks.")

    # --- Query djay ---
    print("Querying djay MediaLibrary.db...")
    djay_index = load_djay_index(tracks)

    # --- Write CSV ---
    fieldnames = ["apple_music_id", "artist", "name", "key", "bpm", "djay_bpm", "djay_manual_bpm", "apple_music_bpm", "djay_am_bpm_diff", "open_key", "essentia_key", "comment", "key_diff"]

    # --- Phase 1: parallel key analysis for tracks with missing profiles ---
    key_cache = analyse(tracks)

    # --- Phase 2: build CSV rows ---
    csv_rows = []
    for track in tracks:
        pid = track["id"]
        djay_data = djay_index.get(pid)
        if djay_data is None:
            continue

        djay_bpm = djay_data["manual_bpm"] or djay_data["bpm"]
        music_bpm = track["bpm"]
        bpm_diff = round(djay_bpm - music_bpm, 2) if djay_bpm != "" and music_bpm != "" else ""
        djay_open_key = djay_data["open_key"]
        essentia_key = consensus_key(key_cache.get(pid, {}))

        csv_rows.append({
            "apple_music_id": pid,
            "artist": track["artist"],
            "name": track["name"],
            "bpm": djay_bpm,
            "djay_bpm": djay_data["bpm"],
            "djay_manual_bpm": djay_data["manual_bpm"],
            "apple_music_bpm": music_bpm,
            "djay_am_bpm_diff": bpm_diff,
            "open_key": djay_open_key,
            "essentia_key": essentia_key,
            "comment": track["comment"],
            "key_diff": _key_diff(djay_open_key, essentia_key, track["comment"]),
        })

    csv_rows.sort(key=lambda r: int(r["key_diff"]) if r["key_diff"] != "" else 0, reverse=True)

    written = 0
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in csv_rows:
            writer.writerow(row)
            written += 1

    print(f"  Wrote {written} tracks.")
    print(f"Exported to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
