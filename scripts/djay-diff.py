#!/usr/bin/env python3
"""
Extract analyzed BPM data from djay's MediaLibrary.db and merge with
comments and BPM from the Apple Music library via osascript.

Usage:
    uv run python extract_bpm.py [--folder NAME]

Options:
    --folder NAME   Filter to songs in a Music library folder (e.g. "Critical Mass")

Database structure:
- `database2` holds all data as binary TSAF blobs
- `secondaryIndex_mediaItemAnalyzedDataIndex` holds indexed BPM values
- All collections share a common hash key per song

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

from lib_apple_music import find_songs_by_folder_name, find_all_songs
from lib_beatunes import lookup_songs, tonalkey_to_str
from lib_djay import load_djay_index
from lib_essentia import analyse, consensus_key, consensus_bpm, ESSENTIA_PROFILES

OUTPUT_PATH = Path(__file__).parent / "songs-djay-diff.csv"


_KEY_PAT = re.compile(r"Key\s+(\d+)([dm])", re.IGNORECASE)


def _parse_open_key(s: str) -> tuple[int, str] | None:
    m = _KEY_PAT.fullmatch(s.strip()) if s else None
    return (int(m.group(1)), m.group(2).lower()) if m else None


def _key_diff(*keys: str) -> str:
    """
    Return the sum of absolute pairwise circular distances among the given
    Open Key strings as a plain integer string.
    Returns "" if fewer than two keys are present.
    """
    available = [v for v in (_parse_open_key(k) for k in keys) if v is not None]
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


def _bpm_diff(*bpms: float | int | str) -> str:
    valid = [float(b) for b in bpms if b != "" and b != 0 and b != 0.0]
    if len(valid) < 2:
        return ""
    return str(round(max(valid) - min(valid), 2))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Export djay BPM data merged with Apple Music metadata.")
    parser.add_argument("--folder", metavar="NAME", help="Filter to songs in this Music library folder")
    args = parser.parse_args()

    # --- Load Music metadata ---
    desc = f"folder '{args.folder}'" if args.folder else "all songs"
    print(f"Loading Apple Music metadata for {desc}...")
    songs = find_songs_by_folder_name(args.folder) if args.folder else find_all_songs()
    print(f"  Loaded metadata for {len(songs)} songs.")

    # --- Query djay ---
    print("Querying djay MediaLibrary.db...")
    djay_index = load_djay_index()
    print(f"  Loaded metadata for {len(djay_index)} songs.")

    # --- Query beaTunes ---
    print("Querying beaTunes database...")
    hex_ids = [song.persistentID for song in songs]
    beatunes_index = lookup_songs(hex_ids)
    print(f"  Loaded metadata for {len(beatunes_index)} songs.")

    # --- Write CSV ---
    fieldnames = [
        "apple_music_id", "artist", "name",
        "djay_bpm", "djay_manual_bpm", "apple_music_bpm",
        "beatunes_bpm", "beatunes_bpm_salience",
        "essentia_bpm", "bpm_rhythm", "bpm_rhythm_confidence", "bpm_percival",
        "bpm_diff",
        "open_key", "essentia_key", "beatunes_key", "comment",
        "edma_key", "edma_strength", "edmm_key", "edmm_strength",
        "bgate_key", "bgate_strength", "braw_key", "braw_strength",
        "shaath_key", "shaath_strength", "temperley_key", "temperley_strength",
        "noland_key", "noland_strength",
        "key_diff",
    ]

    # --- Phase 1: parallel key analysis for songs with missing profiles ---
    essentia_index = analyse(songs)

    # --- Phase 2: build CSV rows ---
    csv_rows = []
    for song in songs:
        pid = song.persistentID
        djay_data = djay_index.get(pid)
        if djay_data is None:
            continue

        # --- Essentia ---
        essentia_entry = essentia_index.get(pid, {})
        essentia_key = consensus_key(essentia_entry)
        essentia_bpm = consensus_bpm(essentia_entry) or ""
        bpm_rhythm = essentia_entry.get("bpm_rhythm", "")
        bpm_rhythm_confidence = essentia_entry.get("bpm_rhythm_confidence", "")
        bpm_percival = essentia_entry.get("bpm_percival", "")
        profile_data = {}
        for p in ESSENTIA_PROFILES:
            profile_data[f"{p}_key"] = essentia_entry.get(f"{p}_key", "")
            profile_data[f"{p}_strength"] = essentia_entry.get(f"{p}_strength", "")

        # --- beaTunes ---
        bt_song = beatunes_index.get(pid)
        beatunes_bpm = bt_song.exactbpm if bt_song and bt_song.exactbpm else ""
        beatunes_bpm_salience = bt_song.exactbpmsalience if bt_song and bt_song.exactbpmsalience else ""
        beatunes_key = tonalkey_to_str(bt_song.tonalkey) if bt_song else ""

        # --- djay ---
        djay_open_key = djay_data.open_key
        djay_effective_bpm = djay_data.manual_bpm or djay_data.bpm

        # --- Diffs ---
        bpm_diff = _bpm_diff(djay_effective_bpm, beatunes_bpm, essentia_bpm)
        profile_keys = {k: v for k, v in profile_data.items() if k.endswith("_key")}
        all_keys = [djay_open_key, beatunes_key] + list(profile_keys.values())
        key_diff = _key_diff(*all_keys)

        csv_rows.append({
            "apple_music_id": pid, "artist": song.artist, "name": song.name,
            "djay_bpm": djay_data.bpm, "djay_manual_bpm": djay_data.manual_bpm,
            "apple_music_bpm": song.bpm, "beatunes_bpm": beatunes_bpm,
            "essentia_bpm": essentia_bpm, "bpm_rhythm": bpm_rhythm,
            "bpm_rhythm_confidence": bpm_rhythm_confidence, "bpm_percival": bpm_percival,
            "beatunes_bpm_salience": beatunes_bpm_salience, "bpm_diff": bpm_diff,
            "open_key": djay_open_key, "essentia_key": essentia_key,
            "beatunes_key": beatunes_key, "comment": song.comment,
            **profile_data, "key_diff": key_diff,
        })

    csv_rows.sort(
        key=lambda r: (
            float(r["bpm_diff"]) if r["bpm_diff"] != "" else 0,
            int(r["key_diff"]) if r["key_diff"] != "" else 0,
        ),
        reverse=True,
    )

    written = 0
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in csv_rows:
            writer.writerow(row)
            written += 1

    print(f"  Wrote {written} songs.")
    print(f"Exported to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
