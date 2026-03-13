#!/usr/bin/env python3
"""
Find songs that can transition FROM a given seed song at the same BPM level,
filtered by BPM tolerance and harmonic key compatibility.

Usage:
    uv run candidates-same [--seed PERSISTENT_ID]
"""
import argparse

from music_stuff.lib.lib_apple_music import find_song_by_id
from music_stuff.lib.lib_transitions import (
    ALLOWED_KEY_TRANSITIONS,
    BPM_TOLERANCE,
    filter_candidates,
    load_playlist,
    print_table,
)


def candidates_same(seed, playlist: str, exclude: str, genres: set[str] | None = None,
              min_rating: int = 80, bpm_lo: float = BPM_TOLERANCE, bpm_hi: float = BPM_TOLERANCE) -> None:
    key = seed.key
    print("\nLoading candidate playlists...")
    candidates = load_playlist(playlist)
    played_ids = {s.id for s in load_playlist(exclude)}

    print_table("Seed", [seed])
    for label, fwd_map in ALLOWED_KEY_TRANSITIONS.items():
        keys = fwd_map.get(key, set())
        results = (
            filter_candidates(candidates, played_ids, seed.bpm - bpm_lo, seed.bpm + bpm_hi, keys, genres, min_rating)
            if keys else []
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
    parser.add_argument(
        "--bpm-lo",
        type=float,
        default=BPM_TOLERANCE,
        help=f"BPM below seed to include (default: {BPM_TOLERANCE})",
    )
    parser.add_argument(
        "--bpm-hi",
        type=float,
        default=BPM_TOLERANCE,
        help=f"BPM above seed to include (default: {BPM_TOLERANCE})",
    )
    args = parser.parse_args()

    print("Looking up seed song...")
    seed = find_song_by_id(args.seed)
    if seed is None:
        raise SystemExit(f"Seed song with ID {args.seed} not found in library.")
    print(f"  {seed.artist} – {seed.name}")

    candidates_same(seed, args.playlist, args.exclude, set(args.genres) if args.genres else None, args.min_rating, args.bpm_lo, args.bpm_hi)


if __name__ == "__main__":
    main()
