#!/usr/bin/env python3
"""
Find songs that can transition INTO a given seed song, filtered by BPM
tolerance and harmonic key compatibility.

Usage:
    uv run python how-to-get-here.py [--seed PERSISTENT_ID]
"""
import argparse
import dataclasses

from music_stuff.lib.lib_apple_music import find_songs_by_playlist_name, find_song_by_id, AppleMusicSong
from music_stuff.lib.lib_beatunes import tonalkey_to_str
from music_stuff.lib.lib_transitions import comment_to_tonalkey, REVERSE_KEY_TRANSITIONS

BPM_TOLERANCE = 12


def _enrich(song: AppleMusicSong) -> dict:
    s = dataclasses.asdict(song)
    s["id"] = song.persistentID
    s["exactbpm"] = float(song.bpm or 0)
    s["tonalkey"] = comment_to_tonalkey(song.comment)
    s["rating_int"] = int(song.rating or 0)
    return s


def _is_relevant(song: dict) -> bool:
    genre = song.get("genre", "") or ""
    if genre not in ("Electronic", "Ambient"):
        return False
    if song.get("rating_int", 0) < 80:
        return False
    comment = (song.get("comment", "") or "").strip()
    if comment == "ignore" or "mixed" in comment.lower():
        return False
    return True


def _filter_candidates(
    candidates: list[dict],
    played_ids: set[int],
    from_bpm: float,
    to_bpm: float,
    tonal_keys: list[int],
) -> list[dict]:
    key_set = set(tonal_keys)
    return [
        s for s in candidates
        if s["id"] not in played_ids
        and _is_relevant(s)
        and from_bpm <= s["exactbpm"] <= to_bpm
        and s["tonalkey"] in key_set
    ]


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
            tonalkey_to_str(s["tonalkey"]),
        ))


def _load_playlist(name: str) -> list[dict]:
    raw = find_songs_by_playlist_name(name)
    return [_enrich(s) for s in raw]


def how_to_get_here(seed: dict) -> None:
    key = seed["tonalkey"]
    print("\nLoading candidate playlists...")
    would_play = _load_playlist("Would Play")
    played_ids = {s["id"] for s in _load_playlist("Critical Mass Played")}
    bpm_lo = seed["exactbpm"] - BPM_TOLERANCE
    bpm_hi = seed["exactbpm"] + BPM_TOLERANCE

    _print_table("Seed", [seed])
    for label, rev_map in REVERSE_KEY_TRANSITIONS.items():
        tonal_keys = rev_map.get(key, [])
        results = (
            _filter_candidates(would_play, played_ids, bpm_lo, bpm_hi, tonal_keys)
            if tonal_keys else []
        )
        _print_table(label.title(), results)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find songs that can transition into a seed song."
    )
    parser.add_argument(
        "--seed",
        type=str,
        default="166EC6D01F2DED99",
        metavar="ID",
        help="Persistent ID of the seed song (default: Tozai)",
    )
    args = parser.parse_args()

    print("Looking up seed song...")
    raw_seed = find_song_by_id(args.seed)
    if raw_seed is None:
        raise SystemExit(f"Seed song with ID {args.seed} not found in library.")
    seed = _enrich(raw_seed)
    print(f"  {seed.get('artist', '')} – {seed.get('name', '')}")

    how_to_get_here(seed)


if __name__ == "__main__":
    main()
