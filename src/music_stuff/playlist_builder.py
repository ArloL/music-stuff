"""Interactive playlist builder — AppState, logic, and CLI entry point."""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass, field
from pathlib import Path

from music_stuff.lib.lib_apple_music import AppleMusicSong, find_song_by_id
from music_stuff.lib.lib_djay import DjaySongData
from music_stuff.lib.lib_transitions import (
    ALLOWED_KEY_TRANSITIONS,
    calculate_transition_score,
    filter_candidates,
    get_transition_type,
    load_playlist,
)

DISPLAY_ORDER = [
    "matching",
    "boost",
    "boost boost",
    "boost boost boost",
    "drop",
    "drop drop",
    "drop drop drop",
]


def _song_dict(s: AppleMusicSong) -> dict:
    return {"key": s.key, "bpm": s.bpm}


@dataclass
class AppState:
    candidate_pool: list[AppleMusicSong]
    played_ids: set[str]  # from exclude playlist (never re-added)
    seed: AppleMusicSong
    history: list[AppleMusicSong]
    bpm_range: float
    genres: set[str] | None
    min_rating: int
    # computed each time seed changes:
    grouped: list[tuple[str, list[AppleMusicSong]]] = field(default_factory=list)
    flat: list[AppleMusicSong] = field(default_factory=list)
    cursor: int = 0


def compute_candidates(
    state: AppState,
) -> tuple[list[tuple[str, list[AppleMusicSong]]], list[AppleMusicSong]]:
    """Return (grouped, flat) candidate lists for the current seed."""
    exclude = state.played_ids | {s.id for s in state.history} | {state.seed.id}
    grouped: list[tuple[str, list[AppleMusicSong]]] = []
    for ttype in DISPLAY_ORDER:
        keys = ALLOWED_KEY_TRANSITIONS[ttype].get(state.seed.key, set())
        matches = filter_candidates(
            state.candidate_pool,
            exclude,
            state.seed.bpm - state.bpm_range,
            state.seed.bpm + state.bpm_range,
            keys,
            state.genres,
            state.min_rating,
        )
        matches.sort(
            key=lambda c: calculate_transition_score(
                _song_dict(state.seed), _song_dict(c)
            ),
            reverse=True,
        )
        grouped.append((ttype, matches))
    flat = [s for _, songs in grouped for s in songs]
    return grouped, flat


def recompute(state: AppState) -> AppState:
    grouped, flat = compute_candidates(state)
    state.grouped = grouped
    state.flat = flat
    state.cursor = 0
    return state


def select_candidate(state: AppState, song: AppleMusicSong) -> AppState:
    """Return a new AppState after selecting *song* as the next track."""
    new_history = state.history + [song]
    new_played = state.played_ids | {song.id}
    new_state = AppState(
        candidate_pool=state.candidate_pool,
        played_ids=new_played,
        seed=song,
        history=new_history,
        bpm_range=state.bpm_range,
        genres=state.genres,
        min_rating=state.min_rating,
    )
    return recompute(new_state)


def undo(state: AppState, original_played_ids: set[str]) -> AppState:
    """Pop the last selection and restore previous seed."""
    if len(state.history) <= 1:
        return state
    new_history = state.history[:-1]
    prev_seed = new_history[-1] if new_history else state.history[0]
    # If we still have history items, the seed is the last one; otherwise
    # we need to know the original seed — callers must not undo past that.
    new_played = original_played_ids | {s.id for s in new_history}
    new_state = AppState(
        candidate_pool=state.candidate_pool,
        played_ids=new_played,
        seed=prev_seed,
        history=new_history,
        bpm_range=state.bpm_range,
        genres=state.genres,
        min_rating=state.min_rating,
    )
    return recompute(new_state)


def save_csv(state: AppState, path: str | Path) -> None:
    """Write the current history to a CSV file.

    history[0] is always the original seed (no incoming transition).
    Transitions are recorded between consecutive entries.
    """
    rows = []
    for i, song in enumerate(state.history):
        if i == 0:
            ttype = ""
            score = ""
        else:
            prev_song = state.history[i - 1]
            ttype = get_transition_type(_song_dict(prev_song), _song_dict(song))
            score = round(
                calculate_transition_score(_song_dict(prev_song), _song_dict(song)), 2
            )
        rows.append(
            {
                "position": i + 1,
                "apple_music_id": song.id,
                "artist": song.artist,
                "name": song.name,
                "key": song.key,
                "bpm": song.bpm,
                "transition_type": ttype,
                "transition_score": score,
            }
        )

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "position",
                "apple_music_id",
                "artist",
                "name",
                "key",
                "bpm",
                "transition_type",
                "transition_score",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def playlist_duration(
    history: list[AppleMusicSong],
    djay_index: dict[str, DjaySongData],
) -> float:
    """Calculate playlist duration using djay automix start points.

    Each track (except the last) contributes its automix start point — the
    position where it begins mixing out and the next track starts.  The last
    track contributes its full duration.  Falls back to song.duration when
    djay data is unavailable for a track.
    """
    if not history:
        return 0.0
    total = 0.0
    for i, song in enumerate(history):
        djay = djay_index.get(song.id)
        if i < len(history) - 1:
            if djay and djay.cue_start_time is not None:
                total += djay.cue_start_time
            else:
                total += song.duration
        else:
            total += song.duration
    return total


def build_initial_state(
    seed: AppleMusicSong,
    pool: list[AppleMusicSong],
    exclude_ids: set[str],
    bpm_range: float,
    genres: set[str] | None,
    min_rating: int,
) -> AppState:
    state = AppState(
        candidate_pool=pool,
        played_ids=exclude_ids | {seed.id},
        seed=seed,
        history=[seed],
        bpm_range=bpm_range,
        genres=genres,
        min_rating=min_rating,
    )
    return recompute(state)


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactive TUI playlist builder")
    parser.add_argument(
        "--seed", help="Apple Music persistent ID of the starting track"
    )
    parser.add_argument("--playlist", default="Would Play", help="Source playlist name")
    parser.add_argument("--exclude", default=None, help="Exclude playlist name")
    parser.add_argument(
        "--genre",
        dest="genres",
        action="append",
        metavar="GENRE",
        help="Allowed genre (repeat for multiple: --genre Techno --genre House)",
    )
    parser.add_argument("--min-rating", type=int, default=80)
    parser.add_argument(
        "--bpm-range",
        type=float,
        default=3.0,
        help="±BPM window around seed to include (adjustable at runtime with +/-)",
    )
    args = parser.parse_args()

    print("Loading playlists…")
    pool = load_playlist(args.playlist)
    exclude_ids = {s.id for s in load_playlist(args.exclude)} if args.exclude else set()

    print("Loading djay library…")
    djay_index: dict = {}
    try:
        from music_stuff.lib.lib_djay import load_djay_index

        djay_index = load_djay_index()
    except Exception as e:
        print(
            f"Warning: could not load djay library ({e}); duration will use track length"
        )

    # Pre-filter: drop songs with empty key
    pool = [s for s in pool if s.key]

    genres = set(args.genres) if args.genres else None

    from music_stuff.tui_playlist_builder import run_tui

    if args.seed:
        seed = find_song_by_id(args.seed)
        if seed is None:
            print(f"Error: no song found with ID {args.seed}", file=sys.stderr)
            sys.exit(1)
        state = build_initial_state(
            seed=seed,
            pool=pool,
            exclude_ids=exclude_ids,
            bpm_range=args.bpm_range,
            genres=genres,
            min_rating=args.min_rating,
        )
        run_tui(
            initial_state=state,
            original_played_ids=exclude_ids | {seed.id},
            pool=pool,
            exclude_ids=exclude_ids,
            bpm_range=args.bpm_range,
            genres=genres,
            min_rating=args.min_rating,
            djay_index=djay_index,
        )
    else:
        run_tui(
            initial_state=None,
            original_played_ids=exclude_ids,
            pool=pool,
            exclude_ids=exclude_ids,
            bpm_range=args.bpm_range,
            genres=genres,
            min_rating=args.min_rating,
            djay_index=djay_index,
        )
