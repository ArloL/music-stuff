#!/usr/bin/env python3
"""
Find songs to transition TO from a given seed song, biasing upward in BPM for
boost-direction transitions and allowing full range for drop-direction transitions.

Usage:
    uv run python where_to_go.py [--seed PERSISTENT_ID]
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

_UPWARD_TRANSITIONS = {"matching", "boost", "boost boost", "boost boost boost"}


def where_to_go(seed, playlist: str, exclude: str, genres: set[str] | None = None, min_rating: int = 80) -> None:
    key = seed.key
    print("\nLoading candidate playlists...")
    candidates = load_playlist(playlist)
    played_ids = {s.id for s in load_playlist(exclude)}
    bpm_hi = seed.bpm + BPM_TOLERANCE

    print_table("Seed", [seed])
    for label, fwd_map in ALLOWED_KEY_TRANSITIONS.items():
        keys = fwd_map.get(key, set())
        if not keys:
            results = []
        else:
            bpm_lo = seed.bpm if label in _UPWARD_TRANSITIONS else seed.bpm - BPM_TOLERANCE
            results = filter_candidates(candidates, played_ids, bpm_lo, bpm_hi, keys, genres, min_rating)
        print_table(label.title(), results)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find songs to play after a seed song, biasing toward higher energy."
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
    seed = find_song_by_id(args.seed)
    if seed is None:
        raise SystemExit(f"Seed song with ID {args.seed} not found in library.")
    print(f"  {seed.get('artist', '')} – {seed.get('name', '')}")

    where_to_go(seed, args.playlist, args.exclude, set(args.genres) if args.genres else None, args.min_rating)


if __name__ == "__main__":
    main()
