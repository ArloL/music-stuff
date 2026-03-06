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
import sys
import re
import subprocess
import json
import argparse
import ctypes
import ctypes.util
from pathlib import Path


SOURCE_DB = Path.home() / "Music/djay/djay Media Library.djayMediaLibrary/MediaLibrary.db"
DB_PATH = Path(__file__).parent / "djay-MediaLibrary.db"
OUTPUT_PATH = Path(__file__).parent / "songs-djay-diff.csv"

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
                                       comment: t.comment() || "", bpm: t.bpm() || 0 }});
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
                                  bpm: t.bpm() || 0 });
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
            }
    return metadata


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
    fieldnames = ["apple_music_id", "artist", "name", "key", "bpm", "djay_bpm", "djay_manual_bpm", "apple_music_bpm", "djay_am_bpm_diff", "key_index", "comment"]

    csv_rows = []
    for pid, meta in music_meta.items():
        djay_data = djay_index.get(pid)
        if djay_data is None:
            continue

        djay_bpm = djay_data["manual_bpm"] or djay_data["bpm"]
        music_bpm = meta["bpm"]
        bpm_diff = round(djay_bpm - music_bpm, 2) if djay_bpm != "" and music_bpm != "" else ""

        csv_rows.append({
            "apple_music_id": pid,
            "artist": meta["artist"],
            "name": meta["name"],
            "bpm": djay_bpm,
            "djay_bpm": djay_data["bpm"],
            "djay_manual_bpm": djay_data["manual_bpm"],
            "apple_music_bpm": music_bpm,
            "djay_am_bpm_diff": bpm_diff,
            "key_index": djay_data["key_index"],
            "comment": meta["comment"],
        })

    csv_rows.sort(key=lambda r: abs(r["djay_am_bpm_diff"]) if r["djay_am_bpm_diff"] != "" else float("inf"), reverse=True)

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
