#!/usr/bin/env python3
"""
Merge BPM and key data from djay, beaTunes, Essentia, and Apple Music into a
single CSV for review and reconciliation.

Usage:
    uv run djay-diff [--folder NAME | --playlist NAME] [--write-bpm] [--write-key]

Defaults to --playlist "Would Play". Outputs to data/songs-djay-diff.csv.

Manual overrides can be placed in data/songs-manual.csv with columns:
    apple_music_id, bpm, key

Database structure (djay MediaLibrary.db):
- `database2` holds all data as binary TSAF blobs
- `secondaryIndex_mediaItemAnalyzedDataIndex` holds indexed BPM values
- All collections share a common hash key per song

TSAF blob format: strings are stored as 0x08 <null-terminated UTF-8 string>
Fields are stored value-first, then key (e.g. "Only Love", "title").

Cross-reference key:
  djay apple_id  "com.apple.iTunes:<decimal>"
  Apple Music Persistent ID  "<HEX>"
  These represent the same value in different bases.
"""

import csv
import sys
import argparse
from pathlib import Path

from music_stuff.lib.lib_apple_music import find_songs_by_folder_name, find_songs_by_playlist_name, set_song_bpm, set_song_key
from music_stuff.lib.lib_beatunes import lookup_songs
from music_stuff.lib.lib_djay import load_djay_index
from music_stuff.lib.lib_consensus import consensus_key, essentia_profile_keys
from music_stuff.lib.lib_essentia import analyse, ESSENTIA_PROFILES
from music_stuff.lib.lib_reccobeats import get_audio_features, spotify_key_to_open_key

OUTPUT_PATH = Path(__file__).parent.parent.parent / "data" / "songs-djay-diff.csv"
MANUAL_BPM_PATH = Path(__file__).parent.parent.parent / "data" / "songs-manual.csv"
SPOTIFY_MAPPING_PATH = Path(__file__).parent.parent.parent / "data" / "spotify-mapping.csv"


def _load_spotify_mapping() -> dict[str, str]:
    """Returns {apple_music_id: spotify_id}."""
    if not SPOTIFY_MAPPING_PATH.exists():
        return {}
    with open(SPOTIFY_MAPPING_PATH, newline="", encoding="utf-8") as f:
        return {
            row["apple_music_id"]: row["spotify_id"]
            for row in csv.DictReader(f)
        }


def _load_manual_overrides() -> dict[str, dict]:
    """Load {apple_music_id: {bpm, key}} overrides from songs-manual.csv."""
    if not MANUAL_BPM_PATH.exists():
        return {}
    with open(MANUAL_BPM_PATH, newline="", encoding="utf-8") as f:
        return {
            row["apple_music_id"]: {"bpm": float(row["bpm"]), "key": row["key"].strip()}
            for row in csv.DictReader(f)
        }


def _parse_open_key(s: str) -> int | None:
    """Parse an Open Key string like '1d' or '12m' into the numeric part."""
    s = s.strip()
    if s and s[:-1].isdigit() and s[-1] in "dm":
        return int(s[:-1])
    return None


def _key_diff(reference: str, *keys: str) -> str:
    """
    Return the sum of circular distances from the reference key to each other key.
    Returns "" if the reference key is missing or no other keys are present.
    """
    ref = _parse_open_key(reference)
    if ref is None:
        return ""
    others = [v for v in (_parse_open_key(k) for k in keys) if v is not None]
    if not others:
        return ""
    total = 0
    for other in others:
        diff = (other - ref) % 12
        if diff > 6:
            diff -= 12
        total += abs(diff)
    return str(total)


def _collect_bpms(*bpms: float | int | str) -> list[float]:
    return [float(b) for b in bpms if b != "" and b != 0 and b != 0.0]


def _bpm_diff(*bpms: float | int | str) -> str:
    valid = _collect_bpms(*bpms)
    if len(valid) < 2:
        return ""
    # Normalise each value toward the median to collapse octave errors,
    # then measure the remaining spread.
    median = sorted(valid)[len(valid) // 2]
    normalised = []
    for b in valid:
        while b > median * 1.5:
            b /= 2
        while b < median / 1.5:
            b *= 2
        normalised.append(b)
    return str(round(max(normalised) - min(normalised), 2))


def _consensus_bpm(*bpms: float | int | str) -> float:
    """Cluster BPMs by octave-equivalence and return the median of the largest cluster."""
    valid = _collect_bpms(*bpms)
    if not valid:
        return ""
    # Build clusters: two values are octave-equivalent if one is within 1.5x of the other
    # Use the first value as the anchor and pull others into its octave
    anchor = sorted(valid)[len(valid) // 2]
    normalised = []
    for b in valid:
        while b > anchor * 1.5:
            b /= 2
        while b < anchor / 1.5:
            b *= 2
        normalised.append(b)
    normalised.sort()
    n = len(normalised)
    median = normalised[n // 2] if n % 2 == 1 else (normalised[n // 2 - 1] + normalised[n // 2]) / 2
    # Pick the octave that the majority of original values live in
    votes_high = sum(1 for b in valid if abs(b - median * 2) < abs(b - median))
    if votes_high >= len(valid) / 2:
        median *= 2
    return round(median, 2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Export djay BPM data merged with Apple Music metadata.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--folder", metavar="NAME",
                       help="Filter to songs in this Music library folder")
    group.add_argument("--playlist", metavar="NAME", default="Would Play",
                       help="Filter to songs in this Music library playlist (default: Would Play)")
    parser.add_argument("--write-bpm", action="store_true", help="Write effective BPM back to Apple Music")
    parser.add_argument("--write-key", action="store_true", help="Write effective key back to Apple Music")
    args = parser.parse_args()

    # --- Load Music metadata ---
    if args.playlist:
        desc = f"playlist '{args.playlist}'"
        loader = lambda: find_songs_by_playlist_name(args.playlist)
    else:
        desc = f"folder '{args.folder}'"
        loader = lambda: find_songs_by_folder_name(args.folder)
    print(f"Loading Apple Music metadata for {desc}...")
    songs = loader()
    print(f"  Loaded metadata for {len(songs)} songs.")

    # --- Query djay ---
    print("Querying djay MediaLibrary.db...")
    djay_index = load_djay_index()
    print(f"  Loaded metadata for {len(djay_index)} songs.")

    # --- Query beaTunes ---
    print("Querying beaTunes database...")
    hex_ids = [song.id for song in songs]
    beatunes_index = lookup_songs(hex_ids)
    print(f"  Loaded metadata for {len(beatunes_index)} songs.")

    # --- Reccobeats ---
    print("Fetching Reccobeats audio features...")
    spotify_mapping = _load_spotify_mapping()
    spotify_ids = [spotify_mapping[s.id] for s in songs if s.id in spotify_mapping]
    reccobeats_index = get_audio_features(spotify_ids)  # {spotify_id: dict}
    reccobeats_by_pid = {
        pid: reccobeats_index[spotify_mapping[pid]]
        for pid in (s.id for s in songs)
        if pid in spotify_mapping and spotify_mapping[pid] in reccobeats_index
    }
    print(f"  Loaded reccobeats data for {len(reccobeats_by_pid)} songs.")

    # --- Write CSV ---
    fieldnames = [
        "apple_music_id", "djay_id", "artist", "name",
        "effective_bpm", "consensus_bpm", "djay_bpm_diff", "bpm_diff",
        "djay_bpm", "djay_manual_bpm", "djay_straight_grid", "apple_music_bpm",
        "beatunes_bpm", "beatunes_bpm_salience", "reccobeats_bpm",
        "bpm_rhythm", "bpm_rhythm_confidence", "bpm_percival",
        "effective_key", "consensus_key", "key_diff",
        "djay_key", "essentia_key", "beatunes_key", "reccobeats_key", "apple_music_key",
        "edma_key", "edma_strength", "edmm_key", "edmm_strength",
        "bgate_key", "bgate_strength", "braw_key", "braw_strength",
        "shaath_key", "shaath_strength", "temperley_key", "temperley_strength",
        "noland_key", "noland_strength",
    ]

    # --- Load manual overrides ---
    manual_overrides = _load_manual_overrides()
    if manual_overrides:
        print(f"Loaded {len(manual_overrides)} manual override(s).")

    # --- Phase 1: parallel key analysis for songs with missing profiles ---
    essentia_index = analyse(songs)

    # --- Phase 2: build CSV rows ---
    csv_rows = []
    for song in songs:
        pid = song.id
        djay_data = djay_index.get(pid)
        if djay_data is None:
            continue

        # --- Essentia ---
        essentia_entry = essentia_index.get(pid, {})
        profile_keys_weighted = essentia_profile_keys(essentia_entry, ESSENTIA_PROFILES)
        essentia_key = consensus_key(essentia_keys=profile_keys_weighted)
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
        beatunes_key = bt_song.key if bt_song else ""

        # --- djay ---
        djay_key = djay_data.key

        # --- Reccobeats ---
        rb = reccobeats_by_pid.get(pid, {})
        reccobeats_bpm = rb.get("tempo", "")
        reccobeats_key = spotify_key_to_open_key(int(rb["mode"]), int(rb["key"])) if rb.get("key") is not None else ""

        # --- Consensus key across all sources ---
        consensus_key_all = consensus_key(
            djay_key=djay_key, beatunes_key=beatunes_key,
            reccobeats_key=reccobeats_key,
            essentia_keys=profile_keys_weighted,
        )

        # --- Manual overrides ---
        manual = manual_overrides.get(pid, {})
        effective_key = manual.get("key") or consensus_key_all

        # --- Diffs ---
        consensus = _consensus_bpm(djay_data.bpm, beatunes_bpm, bpm_rhythm, bpm_percival, reccobeats_bpm)
        effective_bpm = manual.get("bpm") or djay_data.manual_bpm or consensus
        djay_bpm_diff = abs(round(effective_bpm - djay_data.bpm, 0))
        bpm_diff = _bpm_diff(djay_data.bpm, beatunes_bpm, bpm_rhythm, bpm_percival, reccobeats_bpm)
        profile_keys = {k: v for k, v in profile_data.items() if k.endswith("_key")}
        all_keys = [effective_key, djay_key, beatunes_key, reccobeats_key] + list(profile_keys.values())
        key_diff = _key_diff(*all_keys)


        csv_rows.append({
            "apple_music_id": pid, "djay_id": djay_data.id, "artist": song.artist, "name": song.name,
            "djay_bpm": djay_data.bpm, "djay_manual_bpm": djay_data.manual_bpm,
            "djay_straight_grid": djay_data.is_straight_grid,
            "apple_music_bpm": song.bpm, "beatunes_bpm": beatunes_bpm, "reccobeats_bpm": reccobeats_bpm,
            "effective_bpm": effective_bpm, "consensus_bpm": consensus,
            "bpm_rhythm": bpm_rhythm,
            "bpm_rhythm_confidence": bpm_rhythm_confidence, "bpm_percival": bpm_percival,
            "beatunes_bpm_salience": beatunes_bpm_salience, "djay_bpm_diff": djay_bpm_diff, "bpm_diff": bpm_diff,
            "djay_key": djay_key, "essentia_key": essentia_key,
            "beatunes_key": beatunes_key, "reccobeats_key": reccobeats_key,
            "consensus_key": consensus_key_all, "effective_key": effective_key,
            "apple_music_key": song.key,
            **profile_data, "key_diff": key_diff,
        })

    csv_rows.sort(
        key=lambda r: (
            int(r["key_diff"]) if r["key_diff"] != "" else 0,
            float(r["bpm_diff"]) if r["bpm_diff"] != "" else 0,
        ),
        reverse=True,
    )

    written = 0
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore", lineterminator='\n')
        writer.writeheader()
        for row in csv_rows:
            writer.writerow(row)
            written += 1

    print(f"  Wrote {written} songs.")
    print(f"Exported to {OUTPUT_PATH}")

    # --- Write effective BPM back to Apple Music ---
    if args.write_bpm:
        updates = [
            r for r in csv_rows
            if r["effective_bpm"] != "" and int(round(float(r["effective_bpm"]))) != r["apple_music_bpm"]
        ]
        print(f"Writing BPM to Apple Music for {len(updates)} songs...")
        for i, row in enumerate(updates, 1):
            bpm = int(round(float(row["effective_bpm"])))
            set_song_bpm(row["apple_music_id"], bpm)
            print(f"  [{i}/{len(updates)}] {row['artist']} - {row['name']}: {row['apple_music_bpm']} -> {bpm}", end="\r")
        if updates:
            print()

    # --- Write effective key back to Apple Music ---
    if args.write_key:
        updates = [r for r in csv_rows if r["effective_key"] and r["effective_key"] != r["apple_music_key"]]
        print(f"Writing key to Apple Music for {len(updates)} songs...")
        for i, row in enumerate(updates, 1):
            set_song_key(row["apple_music_id"], row["effective_key"])
            print(f"  [{i}/{len(updates)}] {row['artist']} - {row['name']}: {row['apple_music_key']} -> {row['effective_key']}", end="\r")
        if updates:
            print()


if __name__ == "__main__":
    main()
