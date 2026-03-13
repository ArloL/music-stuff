#!/usr/bin/env python3
"""
Find songs that can transition FROM a given seed song at the same BPM level,
filtered by BPM tolerance and harmonic key compatibility.

Usage:
    uv run python stay_here.py [--seed PERSISTENT_ID]
"""
import argparse

from music_stuff.lib.lib_apple_music import find_song_by_id
from music_stuff.lib.lib_transitions import (
    ALLOWED_KEY_TRANSITIONS,
    BPM_TOLERANCE,
    enrich_song,
    filter_candidates,
    load_playlist,
    print_table,
)


def stay_here(seed: dict, playlist: str, exclude: str, genres: set[str] | None = None, min_rating: int = 80) -> None:
    key = seed["tonalkey"]
    print("\nLoading candidate playlists...")
    candidates = load_playlist(playlist)
    played_ids = {s["id"] for s in load_playlist(exclude)}
    bpm_lo = seed["exactbpm"] - BPM_TOLERANCE
    bpm_hi = seed["exactbpm"] + BPM_TOLERANCE

    print_table("Seed", [seed])
    for label, fwd_map in ALLOWED_KEY_TRANSITIONS.items():
        tonal_keys = fwd_map.get(key, [])
        results = (
            filter_candidates(candidates, played_ids, bpm_lo, bpm_hi, tonal_keys, genres, min_rating)
            if tonal_keys else []
        )
        print_table(label.title(), results)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find songs to play after a seed song at the same energy level."
    )
    parser.add_argument(
        "--seed",
        type=str,
        default="166EC6D01F2DED99",
        metavar="ID",
        help="Persistent ID of the seed song (default: Tozai)",
    )
    parser.add_argument(
        "--playlist",
        type=str,
        default="Would Play",
        help="Candidate playlist to search (default: 'Would Play')",
    )
    parser.add_argument(
        "--exclude",
        type=str,
        default="Critical Mass Played",
        help="Playlist of songs to exclude (default: 'Critical Mass Played')",
    )
    parser.add_argument(
        "--genres",
        nargs="+",
        metavar="GENRE",
        default=None,
        help="Genres to include (default: all genres)",
    )
    parser.add_argument(
        "--min-rating",
        type=int,
        default=80,
        help="Minimum song rating to include (default: 80)",
    )
    args = parser.parse_args()

    print("Looking up seed song...")
    raw_seed = find_song_by_id(args.seed)
    if raw_seed is None:
        raise SystemExit(f"Seed song with ID {args.seed} not found in library.")
    seed = enrich_song(raw_seed)
    print(f"  {seed.get('artist', '')} – {seed.get('name', '')}")

    stay_here(seed, args.playlist, args.exclude, set(args.genres) if args.genres else None, args.min_rating)


if __name__ == "__main__":
    main()
