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
  Apple Music (via localMediaItemLocations blob):  title, artist, appleMusicBpm, duration

Usage:
    uv run djay-export-blobs [--output-dir DIR] [--playlist NAME]
"""

import argparse
import json
import sqlite3
from pathlib import Path

from music_stuff.lib.lib_apple_music import find_all_songs, find_songs_by_playlist_name
from music_stuff.lib.lib_djay import DB_PATH, _extract_persistent_ids

COLLECTIONS = [
    "localMediaItemLocations",
    "mediaItemAnalyzedData",
    "mediaItemTitleIDs",
    "mediaItemUserData",
]


def export_blobs(output_dir: Path, playlist: str | None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Loading Apple Music library...")
    if playlist:
        songs = find_songs_by_playlist_name(playlist)
        am_index = {song.id: song for song in songs}
        print(f"  {len(am_index)} tracks from playlist '{playlist}'")
    else:
        am_index = {song.id: song for song in find_all_songs()}
        print(f"  {len(am_index)} tracks loaded")

    # Resolve which djay keys belong to the target songs by scanning
    # localMediaItemLocations blobs for matching Apple Music persistent IDs.
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        location_rows = con.execute(
            "SELECT key, data FROM database2 WHERE collection = 'localMediaItemLocations'"
        ).fetchall()

        # djay key -> first matched AppleMusicSong
        key_to_song: dict[str, object] = {}
        for row in location_rows:
            blob = bytes(row["data"]) if row["data"] is not None else b""
            for pid in _extract_persistent_ids(blob):
                song = am_index.get(pid)
                if song is not None:
                    key_to_song[row["key"]] = (pid, song)
                    break

        allowed_keys = set(key_to_song)

        for collection in COLLECTIONS:
            rows = con.execute(
                "SELECT key, data FROM database2 WHERE collection = ? ORDER BY key",
                (collection,),
            ).fetchall()
            written = 0
            for row in rows:
                if row["key"] not in allowed_keys:
                    continue
                data_bytes = bytes(row["data"]) if row["data"] is not None else b""
                out_path = output_dir / f"{row['key']}-{collection}.bin"
                out_path.write_bytes(data_bytes)
                written += 1
            print(f"{output_dir}/<key>-{collection}.bin  ({written} files)")

        index: dict[str, dict] = {}

        analyzed_rows = con.execute("""
            SELECT d.key, si.bpm, si.keySignatureIndex
            FROM database2 d
            JOIN secondaryIndex_mediaItemAnalyzedDataIndex si ON si.rowid = d.rowid
            WHERE d.collection = 'mediaItemAnalyzedData'
        """).fetchall()
        for row in analyzed_rows:
            if row["key"] not in allowed_keys:
                continue
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
            if row["key"] not in allowed_keys:
                continue
            entry = {}
            if row["manualBPM"] is not None:
                entry["manualBPM"] = row["manualBPM"]
            if row["tags"] is not None:
                entry["tags"] = row["tags"]
            if entry:
                index.setdefault(row["key"], {}).update(entry)

        for djay_key, (pid, song) in key_to_song.items():
            entry = {"appleMusicId": int(pid, 16), "title": song.name, "artist": song.artist}
            if song.bpm:
                entry["appleMusicBpm"] = song.bpm
            if song.duration:
                entry["duration"] = song.duration
            index.setdefault(djay_key, {}).update(entry)

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
        help="Directory to write *.bin and *.json files (default: data/bin)",
    )
    parser.add_argument(
        "--playlist",
        metavar="NAME",
        help="Limit export to songs in this Apple Music playlist",
    )
    args = parser.parse_args()
    export_blobs(args.output_dir, args.playlist)


if __name__ == "__main__":
    main()
