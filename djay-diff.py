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

import sqlite3
import csv
import os
import sys
import re
import subprocess
import json
import argparse
import ctypes
import ctypes.util
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname


SOURCE_DB = Path.home() / "Music/djay/djay Media Library.djayMediaLibrary/MediaLibrary.db"

DJAY_KEY_INDEX_TO_OPEN_KEY = {
    0: "1d",  1: "1m",
    2: "8d",  3: "8m",
    4: "3d",  5: "3m",
    6: "10d", 7: "10m",
    8: "5d",  9: "5m",
    10: "12d", 11: "12m",
    12: "7d", 13: "7m",
    14: "2d", 15: "2m",
    16: "9d", 17: "9m",
    18: "4d", 19: "4m",
    20: "11d", 21: "11m",
    22: "6d", 23: "6m",
}
DB_PATH = Path(__file__).parent / "djay-MediaLibrary.db"
OUTPUT_PATH = Path(__file__).parent / "songs-djay-diff.csv"
KEY_CACHE_PATH = Path(__file__).parent / "essentia-key-cache.csv"

_libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
_libc.clonefile.restype = ctypes.c_int
_libc.clonefile.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint32]


def _clonefile(src: Path, dst: Path) -> None:
    """APFS copy-on-write clone via clonefile(2). Destination must not exist."""
    dst.unlink(missing_ok=True)
    ret = _libc.clonefile(str(src).encode(), str(dst).encode(), 0)
    if ret != 0:
        raise OSError(ctypes.get_errno(), f"clonefile({src} -> {dst})")


# ---------------------------------------------------------------------------
# Apple Music — osascript
# ---------------------------------------------------------------------------

def _run_jxa(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-l", "JavaScript"],
        input=script,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def _hex_id_to_int(hex_id: str) -> int | None:
    """Convert a hex persistent ID string to a signed 64-bit int."""
    try:
        value = int(hex_id, 16)
        if value >= (1 << 63):
            value -= (1 << 64)
        return value
    except (ValueError, TypeError):
        return None


def load_music_metadata(folder_name: str | None = None) -> dict[int, dict]:
    """
    Query the running Music app for track metadata.
    If folder_name is given, only returns tracks in that library folder.
    Returns dict mapping persistent_id (signed int) -> {name, artist, comment, bpm}.
    """
    if folder_name is not None:
        script = f"""
            const music = Application("Music");
            const folder = music.playlists.whose({{ name: {{ _equals: {json.dumps(folder_name)} }} }})[0];
            const folderID = folder.persistentID();
            const seen = new Set();
            const result = [];
            for (const pl of music.playlists()) {{
                try {{
                    if (!pl.parent || pl.parent().persistentID() !== folderID) continue;
                    for (const t of pl.tracks()) {{
                        const id = t.persistentID();
                        if (seen.has(id)) continue;
                        seen.add(id);
                        result.push({{ id, name: t.name() || "", artist: t.artist() || "",
                                       comment: t.comment() || "", bpm: t.bpm() || 0,
                                       location: t.location() ? t.location().toString() : "" }});
                    }}
                }} catch (e) {{}}
            }}
            JSON.stringify(result);
        """
    else:
        script = """
            const music = Application("Music");
            const result = [];
            for (const t of music.libraryPlaylists[0].tracks()) {
                try {
                    result.push({ id: t.persistentID(), name: t.name() || "",
                                  artist: t.artist() || "", comment: t.comment() || "",
                                  bpm: t.bpm() || 0,
                                  location: t.location() ? t.location().toString() : "" });
                } catch (e) {}
            }
            JSON.stringify(result);
        """
    records = json.loads(_run_jxa(script))
    metadata: dict[int, dict] = {}
    for rec in records:
        pid = _hex_id_to_int(rec["id"])
        if pid is not None:
            metadata[pid] = {
                "name": rec["name"],
                "artist": rec["artist"],
                "comment": rec["comment"],
                "bpm": rec["bpm"] or "",
                "location": rec["location"],
            }
    return metadata


# ---------------------------------------------------------------------------
# Audio key detection — essentia
# ---------------------------------------------------------------------------

# pip install essentia  (or: brew install essentia on macOS)
# Maps essentia key names to Open Key numbers for major (d) and minor (m).
# Includes both sharp and flat spellings since KeyExtractor may return either.
_ESSENTIA_MAJOR_TO_OPEN_KEY: dict[str, str] = {
    "C": "1d",  "G": "2d",  "D": "3d",   "A": "4d",
    "E": "5d",  "B": "6d",  "F#": "7d",  "Gb": "7d",
    "C#": "8d", "Db": "8d", "G#": "9d",  "Ab": "9d",
    "D#": "10d","Eb": "10d","A#": "11d", "Bb": "11d",
    "F": "12d",
}
_ESSENTIA_MINOR_TO_OPEN_KEY: dict[str, str] = {
    "A": "1m",  "E": "2m",  "B": "3m",   "F#": "4m",  "Gb": "4m",
    "C#": "5m", "Db": "5m", "G#": "6m",  "Ab": "6m",
    "D#": "7m", "Eb": "7m", "A#": "8m",  "Bb": "8m",
    "F": "9m",  "C": "10m", "G": "11m",  "D": "12m",
}


ESSENTIA_PROFILES = ["edma", "edmm", "bgate", "braw", "shaath", "temperley", "noland"]

# profile results type: profile -> (open_key, strength)
KeyProfileResults = dict[str, tuple[str, float]]


def _location_to_path(location: str) -> Path | None:
    if not location:
        return None
    if location.startswith("file://"):
        return Path(url2pathname(urlparse(location).path))
    return Path(location)


def load_key_cache() -> dict[int, KeyProfileResults]:
    """Load apple_music_id -> {profile: (open_key, strength)} from the cache CSV.
    Loads all profile columns present in the file, regardless of current ESSENTIA_PROFILES."""
    if not KEY_CACHE_PATH.exists():
        return {}
    with open(KEY_CACHE_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "apple_music_id" not in reader.fieldnames:
            return {}
        all_profiles = [
            col[:-4] for col in reader.fieldnames if col.endswith("_key") and col != "apple_music_id"
        ]
        result: dict[int, KeyProfileResults] = {}
        for row in reader:
            pid = int(row["apple_music_id"])
            result[pid] = {
                p: (row[f"{p}_key"], float(row.get(f"{p}_strength") or 0.0))
                for p in all_profiles
            }
        return result


def write_key_cache(cache: dict[int, KeyProfileResults]) -> None:
    """Write the cache CSV sorted by apple_music_id, preserving all profiles in the data."""
    all_profiles: list[str] = []
    seen: set[str] = set()
    for profile_results in cache.values():
        for p in profile_results:
            if p not in seen:
                all_profiles.append(p)
                seen.add(p)
    fieldnames = ["apple_music_id"] + [f"{p}_{s}" for p in all_profiles for s in ("key", "strength")]
    with open(KEY_CACHE_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for pid in sorted(cache):
            row: dict = {"apple_music_id": pid}
            for p in all_profiles:
                open_key, strength = cache[pid].get(p, ("", 0.0))
                row[f"{p}_key"] = open_key
                row[f"{p}_strength"] = strength
            writer.writerow(row)


def detect_key_essentia(location: str, profiles: list[str]) -> KeyProfileResults:
    """
    Detect musical key using the given essentia KeyExtractor profiles.
    Returns dict mapping profile name -> (open_key, strength).
    """
    if not profiles:
        return {}
    try:
        import essentia.standard as es  # type: ignore
    except ImportError:
        return {}

    path = _location_to_path(location)
    if path is None or not path.exists():
        return {}

    try:
        audio = es.MonoLoader(filename=str(path))()
    except Exception:
        return {}

    results: KeyProfileResults = {}
    for profile in profiles:
        try:
            key, scale, strength = es.KeyExtractor(profileType=profile)(audio)
            mapping = _ESSENTIA_MAJOR_TO_OPEN_KEY if scale == "major" else _ESSENTIA_MINOR_TO_OPEN_KEY
            open_key = mapping.get(key, "")
            results[profile] = (f"Key {open_key}" if open_key else "", round(float(strength), 4))
        except Exception:
            results[profile] = ("", 0.0)
    return results


def _consensus_key(profile_results: KeyProfileResults) -> str:
    """Strength-weighted majority vote across profiles. Returns the winning open key."""
    votes: dict[str, float] = {}
    for open_key, strength in profile_results.values():
        if open_key:
            votes[open_key] = votes.get(open_key, 0.0) + strength
    return max(votes, key=lambda k: votes[k]) if votes else ""


# ---------------------------------------------------------------------------
# djay MediaLibrary.db parsing
# ---------------------------------------------------------------------------

_APPLE_ID_RE = re.compile(rb'\x08com\.apple\.(?:iTunes|Music):(-?\d+)\x00')


def extract_persistent_ids(data: bytes) -> list[int]:
    """Extract Apple Music persistent IDs (signed 64-bit) from a TSAF blob."""
    result = []
    for m in _APPLE_ID_RE.finditer(data):
        value = int(m.group(1))
        if value >= (1 << 63):
            value -= (1 << 64)
        result.append(value)
    return result


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

    # --- Copy database ---
    if not SOURCE_DB.exists():
        print(f"Error: djay database not found: {SOURCE_DB}", file=sys.stderr)
        sys.exit(1)
    print(f"Cloning database from {SOURCE_DB} ...")
    _clonefile(SOURCE_DB, DB_PATH)
    for suffix in ("-wal", "-shm"):
        src = Path(str(SOURCE_DB) + suffix)
        if src.exists():
            _clonefile(src, Path(str(DB_PATH) + suffix))
    print("  Done.")

    # --- Load Music metadata ---
    desc = f"folder '{args.folder}'" if args.folder else "all tracks"
    print(f"Loading Apple Music metadata for {desc}...")
    music_meta = load_music_metadata(args.folder)
    print(f"  Loaded metadata for {len(music_meta)} tracks.")

    # --- Query djay ---
    print("Querying djay MediaLibrary.db...")
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row

    rows = con.execute("""
        SELECT
            bpm_idx.bpm,
            bpm_idx.manualBPM,
            bpm_idx.keySignatureIndex,
            loc.data AS location_blob
        FROM secondaryIndex_mediaItemAnalyzedDataIndex AS bpm_idx
        JOIN database2 AS analyzed
            ON analyzed.rowid = bpm_idx.rowid
            AND analyzed.collection = 'mediaItemAnalyzedData'
        JOIN database2 AS loc
            ON loc.key = analyzed.key
            AND loc.collection = 'localMediaItemLocations'
        WHERE bpm_idx.bpm IS NOT NULL
    """).fetchall()
    con.close()

    # Build djay index: persistent_id -> djay analysis data
    djay_index: dict[int, dict] = {}
    for row in rows:
        for pid in extract_persistent_ids(bytes(row["location_blob"])):
            if pid in djay_index or pid not in music_meta:
                continue
            djay_index[pid] = {
                "bpm": round(row["bpm"], 2) if row["bpm"] else "",
                "manual_bpm": round(row["manualBPM"], 2) if row["manualBPM"] else "",
                "key_index": row["keySignatureIndex"],
            }



    # --- Write CSV ---
    fieldnames = ["apple_music_id", "artist", "name", "key", "bpm", "djay_bpm", "djay_manual_bpm", "apple_music_bpm", "djay_am_bpm_diff", "open_key", "essentia_key", "comment", "key_diff"]

    key_cache = load_key_cache()
    print(f"  Key cache: {len(key_cache)} entries loaded from {KEY_CACHE_PATH.name}")

    # --- Phase 1: parallel key analysis for tracks with missing profiles ---
    done = 0
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = {
            executor.submit(detect_key_essentia, meta["location"], [p for p in ESSENTIA_PROFILES if p not in key_cache.get(pid, {})]): pid
            for pid, meta in music_meta.items()
            if pid in djay_index
        }
        for future in as_completed(futures):
            pid = futures[future]
            key_cache.setdefault(pid, {}).update(future.result())
            done += 1
            print(f"  Analysing keys [{done}/{len(futures)}]", end="\r")
    print()

    # --- Phase 2: build CSV rows ---
    csv_rows = []
    for pid, meta in music_meta.items():
        djay_data = djay_index.get(pid)
        if djay_data is None:
            continue

        djay_bpm = djay_data["manual_bpm"] or djay_data["bpm"]
        music_bpm = meta["bpm"]
        bpm_diff = round(djay_bpm - music_bpm, 2) if djay_bpm != "" and music_bpm != "" else ""
        djay_open_key = ("Key " + DJAY_KEY_INDEX_TO_OPEN_KEY[djay_data["key_index"]]) if djay_data["key_index"] in DJAY_KEY_INDEX_TO_OPEN_KEY else ""
        essentia_key = _consensus_key(key_cache.get(pid, {}))

        csv_rows.append({
            "apple_music_id": pid,
            "artist": meta["artist"],
            "name": meta["name"],
            "bpm": djay_bpm,
            "djay_bpm": djay_data["bpm"],
            "djay_manual_bpm": djay_data["manual_bpm"],
            "apple_music_bpm": music_bpm,
            "djay_am_bpm_diff": bpm_diff,
            "open_key": djay_open_key,
            "essentia_key": essentia_key,
            "comment": meta["comment"],
            "key_diff": _key_diff(djay_open_key, essentia_key, meta["comment"]),
        })

    csv_rows.sort(key=lambda r: int(r["key_diff"]) if r["key_diff"] != "" else 0, reverse=True)

    written = 0
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in csv_rows:
            writer.writerow(row)
            written += 1

    write_key_cache(key_cache)
    print(f"  Wrote {written} tracks.")
    print(f"Exported to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
