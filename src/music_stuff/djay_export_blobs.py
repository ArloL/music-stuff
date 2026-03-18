#!/usr/bin/env python3
"""
Export raw binary blobs from djay's MediaLibrary.db for the four collections:
  localMediaItemLocations, mediaItemAnalyzedData, mediaItemTitleIDs, mediaItemUserData

Each song+collection is written to: <hex_key>-<collection>.bin
One JSON file per song is written to: <hex_key>.json

Binary file format: raw data blob only (the key is encoded in the filename).

Per-song JSON contains available secondary-index columns:
  secondaryIndex_mediaItemAnalyzedDataIndex: bpm, keySignatureIndex
  secondaryIndex_mediaItemUserDataIndex:     manualBPM, tags
  (secondaryIndex_mediaItemAnalyzedDataIndex.manualBPM is always NULL — skipped)

Usage:
    uv run djay-export-blobs [--output-dir DIR]
"""

import argparse
import json
import sqlite3
from pathlib import Path

from music_stuff.lib.lib_djay import DB_PATH

COLLECTIONS = [
    "localMediaItemLocations",
    "mediaItemAnalyzedData",
    "mediaItemTitleIDs",
    "mediaItemUserData",
]


def export_blobs(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        for collection in COLLECTIONS:
            rows = con.execute(
                "SELECT key, data FROM database2 WHERE collection = ? ORDER BY key",
                (collection,),
            ).fetchall()
            for row in rows:
                data_bytes = bytes(row["data"]) if row["data"] is not None else b""
                out_path = output_dir / f"{row['key']}-{collection}.bin"
                out_path.write_bytes(data_bytes)
            print(f"{output_dir}/<key>-{collection}.bin  ({len(rows)} files)")

        index: dict[str, dict] = {}

        analyzed_rows = con.execute("""
            SELECT d.key, si.bpm, si.keySignatureIndex
            FROM database2 d
            JOIN secondaryIndex_mediaItemAnalyzedDataIndex si ON si.rowid = d.rowid
            WHERE d.collection = 'mediaItemAnalyzedData'
        """).fetchall()
        for row in analyzed_rows:
            entry: dict = {}
            if row["bpm"] is not None:
                entry["bpm"] = row["bpm"]
            if row["keySignatureIndex"] is not None:
                entry["keySignatureIndex"] = row["keySignatureIndex"]
            if entry:
                index.setdefault(row["key"], {}).update(entry)

        userdata_rows = con.execute("""
            SELECT d.key, si.manualBPM, si.tags
            FROM database2 d
            JOIN secondaryIndex_mediaItemUserDataIndex si ON si.rowid = d.rowid
            WHERE d.collection = 'mediaItemUserData'
        """).fetchall()
        for row in userdata_rows:
            entry = {}
            if row["manualBPM"] is not None:
                entry["manualBPM"] = row["manualBPM"]
            if row["tags"] is not None:
                entry["tags"] = row["tags"]
            if entry:
                index.setdefault(row["key"], {}).update(entry)

        for song_key, fields in index.items():
            song_path = output_dir / f"{song_key}.json"
            song_path.write_text(json.dumps(fields, indent=2))
        print(f"{output_dir}/<key>.json  ({len(index)} files)")
    finally:
        con.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/bin"),
        help="Directory to write key-*.bin and index.json (default: data/)",
    )
    args = parser.parse_args()
    export_blobs(args.output_dir)


if __name__ == "__main__":
    main()
