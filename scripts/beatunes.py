#!/usr/bin/env python3
"""
Python rewrite of BeatunesDbviewerApplication.java.
Uses lib_apple_music.py (Apple Music via JXA) instead of the beaTunes H2 database.

Usage:
    uv run python beatunes.py [--seed PERSISTENT_ID]
"""
import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path

from lib_apple_music import find_tracks_by_playlist_name, find_track_by_id
from lib_essentia import analyse, consensus_key, consensus_bpm
from lib_transitions import ALLOWED_KEY_TRANSITIONS

BPM_TOLERANCE = 12
_KEY_PAT = re.compile(r"Key\s+(\d+)([dm])", re.IGNORECASE)
OUTPUT_DIR = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Key encoding helpers
#
# beaTunes stores Open Key notation in the Apple Music comment field as
# "Key Nd" (major) or "Key Nm" (minor), e.g. "Key 6d".
# Internally the 1-24 integer uses:  odd = major (d),  even = minor (m)
#   "Nd" → 2N-1   e.g. "6d" → 11
#   "Nm" → 2N     e.g. "6m" → 12
# ---------------------------------------------------------------------------

def _comment_to_tonalkey(comment: str) -> int | None:
    if not comment:
        return None
    m = _KEY_PAT.search(comment)
    if not m:
        return None
    n, mode = int(m.group(1)), m.group(2).lower()
    return 2 * n - 1 if mode == 'd' else 2 * n


def _tonalkey_to_str(key: int | None) -> str:
    if not key:
        return ""
    n = (key + 1) // 2
    mode = "d" if key % 2 != 0 else "m"
    return f"Key {n}{mode}"


# ---------------------------------------------------------------------------
# Track enrichment / filtering
# ---------------------------------------------------------------------------

def _enrich(track: dict, essentia_cache: dict) -> dict:
    t = dict(track)
    t["id"] = t["persistentID"]
    entry = essentia_cache.get(t["id"], {})
    t["exactbpm"] = consensus_bpm(entry)
    t["tonalkey"] = _comment_to_tonalkey(consensus_key(entry))
    t["rating_int"] = int(t.get("rating") or 0)
    return t


def _is_relevant(track: dict) -> bool:
    genre = track.get("genre", "") or ""
    if genre not in ("Electronic", "Ambient"):
        return False
    if track.get("rating_int", 0) < 80:
        return False
    comment = (track.get("comment", "") or "").strip()
    if comment == "ignore" or "mixed" in comment.lower():
        return False
    return True


# ---------------------------------------------------------------------------
# Reverse transition maps  (A→B in forward means B→A in reverse)
# Used by howToGetHere to find songs that can transition INTO the seed.
# ---------------------------------------------------------------------------

def _build_reverse_transitions() -> dict[str, dict[int, list[int]]]:
    result = {}
    for ttype, forward in ALLOWED_KEY_TRANSITIONS.items():
        rev: dict[int, list[int]] = defaultdict(list)
        for src, targets in forward.items():
            for tgt in targets:
                rev[tgt].append(src)
        result[ttype] = dict(rev)
    return result


REVERSE_TRANSITIONS = _build_reverse_transitions()


# ---------------------------------------------------------------------------
# Playlist queries
# ---------------------------------------------------------------------------

def _load_playlist(name: str) -> list[dict]:
    raw = find_tracks_by_playlist_name(name)
    cache = analyse(raw)
    return [_enrich(t, cache) for t in raw]


def _filter_candidates(
    candidates: list[dict],
    played_ids: set[int],
    from_bpm: float,
    to_bpm: float,
    tonal_keys: list[int],
) -> list[dict]:
    key_set = set(tonal_keys)
    return [
        t for t in candidates
        if t["id"] not in played_ids
        and _is_relevant(t)
        and from_bpm <= t["exactbpm"] <= to_bpm
        and t["tonalkey"] in key_set
    ]


# ---------------------------------------------------------------------------
# CSV output
# ---------------------------------------------------------------------------

def write_playlist_to_file(filename: str, playlist_name: str) -> None:
    print(f"Writing '{playlist_name}' → {filename} ...")
    tracks = _load_playlist(playlist_name)
    output = OUTPUT_DIR / filename
    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["apple_music_id", "artist", "name", "key", "bpm"]
        )
        writer.writeheader()
        for t in tracks:
            writer.writerow({
                "apple_music_id": t["id"],
                "artist": t.get("artist", ""),
                "name": t.get("name", ""),
                "key": t["tonalkey"] or "",
                "bpm": t["exactbpm"] or "",
            })
    print(f"  Wrote {len(tracks)} tracks.")


# ---------------------------------------------------------------------------
# Terminal table display
# ---------------------------------------------------------------------------

def _print_table(title: str, songs: list[dict]) -> None:
    print(f"\n= {title} =")
    if not songs:
        print("  (none)")
        return
    col_id   = max(len(str(s["id"])) for s in songs)
    col_art  = max((len(s.get("artist", "") or "") for s in songs), default=6)
    col_name = max((len(s.get("name", "") or "") for s in songs), default=4)
    row = f"{{:<{col_id}}}  {{:<{col_art}}}  {{:<{col_name}}}  {{:<7}}  {{:<8}}"
    header = row.format("ID", "Artist", "Name", "BPM", "Key")
    print(header)
    print("-" * len(header))
    for s in songs:
        print(row.format(
            str(s["id"]),
            s.get("artist", "") or "",
            s.get("name", "") or "",
            f"{s['exactbpm']:.2f}",
            _tonalkey_to_str(s["tonalkey"]),
        ))


# ---------------------------------------------------------------------------
# howToGetHere — find songs that can transition INTO the seed song
# ---------------------------------------------------------------------------

def how_to_get_here(seed: dict) -> None:
    key = seed["tonalkey"]
    print("\nLoading candidate playlists...")
    would_play = _load_playlist("Would Play")
    played_ids = {t["id"] for t in _load_playlist("Critical Mass Played")}
    bpm_lo = seed["exactbpm"] - BPM_TOLERANCE
    bpm_hi = seed["exactbpm"] + BPM_TOLERANCE

    _print_table("Seed", [seed])
    for label, rev_map in REVERSE_TRANSITIONS.items():
        tonal_keys = rev_map.get(key, [])
        results = (
            _filter_candidates(would_play, played_ids, bpm_lo, bpm_hi, tonal_keys)
            if tonal_keys else []
        )
        _print_table(label.title(), results)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Show compatible predecessor songs and export playlist CSVs."
    )
    parser.add_argument(
        "--seed",
        type=str,
        default="166EC6D01F2DED99",
        metavar="ID",
        help="Persistent ID of the seed song (default: Tozai)",
    )
    args = parser.parse_args()

    write_playlist_to_file("songs-critical-mass-2025-08.csv", "Critical Mass 2025-08")
    write_playlist_to_file("songs-critical-mass-next.csv", "Critical Mass Next")
    write_playlist_to_file("songs-would-play-and-didnt.csv", "Would Play And Didnt")
    write_playlist_to_file("songs-would-play.csv", "Would Play")

    print("\nLooking up seed song...")
    raw_seed = find_track_by_id(args.seed)
    if raw_seed is None:
        raise SystemExit(f"Seed song with ID {args.seed} not found in library.")
    cache = analyse([raw_seed])
    seed = _enrich(raw_seed, cache)
    print(f"  {seed.get('artist', '')} – {seed.get('name', '')}")

    how_to_get_here(seed)


if __name__ == "__main__":
    main()
