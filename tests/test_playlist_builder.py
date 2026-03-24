"""Tests for playlist_builder AppState logic. No TUI instantiation."""

from __future__ import annotations

import csv
from dataclasses import dataclass

from music_stuff.playlist_builder import (
    AppState,
    _song_dict,
    compute_candidates,
    save_csv,
    select_candidate,
    undo,
)

# ---------------------------------------------------------------------------
# Minimal song stub — same field names as AppleMusicSong
# ---------------------------------------------------------------------------


@dataclass
class _Song:
    id: str
    bpm: float
    key: str
    name: str = "Track"
    artist: str = "Artist"
    comment: str = ""
    rating: int = 100
    genre: str = "Electronic"
    location: str = ""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_state(
    seed, pool, played_ids=None, bpm_range=12.0, genres=None, min_rating=80
):
    s = AppState(
        candidate_pool=pool,
        played_ids=played_ids or set(),
        seed=seed,
        history=[seed],
        bpm_range=bpm_range,
        genres=genres,
        min_rating=min_rating,
    )
    from music_stuff.playlist_builder import recompute

    return recompute(s)


# ---------------------------------------------------------------------------
# _song_dict
# ---------------------------------------------------------------------------


def test_song_dict_returns_key_and_bpm():
    s = _Song("1", 128, "6d")
    assert _song_dict(s) == {"key": "6d", "bpm": 128}


# ---------------------------------------------------------------------------
# compute_candidates grouping
# ---------------------------------------------------------------------------


def test_compute_candidates_groups_by_transition_type():
    seed = _Song("seed", 128.0, "6d")
    # 6d → 7d is "boost", 6d → 6d is "matching"
    matching = _Song("m1", 128.0, "6d")
    boost = _Song("b1", 128.0, "7d")
    pool = [matching, boost]
    state = _make_state(seed, pool)

    grouped, flat = compute_candidates(state)
    group_dict = {label: songs for label, songs in grouped}

    assert matching in group_dict["matching"]
    assert boost in group_dict["boost"]
    # seed itself is excluded
    assert seed not in flat


def test_compute_candidates_excludes_history():
    seed = _Song("seed", 128.0, "6d")
    already_played = _Song("p1", 128.0, "6d")
    state = _make_state(seed, [already_played])
    # put already_played in history
    state.history = [seed, already_played]
    grouped, flat = compute_candidates(state)
    assert already_played not in flat


def test_compute_candidates_excludes_played_ids():
    seed = _Song("seed", 128.0, "6d")
    excluded = _Song("ex1", 128.0, "6d")
    state = _make_state(seed, [excluded], played_ids={"ex1"})
    _, flat = compute_candidates(state)
    assert excluded not in flat


def test_compute_candidates_respects_bpm_range():
    seed = _Song("seed", 128.0, "6d")
    too_slow = _Song("slow", 100.0, "6d")  # 28 BPM below, outside default ±12
    in_range = _Song("good", 130.0, "6d")
    state = _make_state(seed, [too_slow, in_range])
    _, flat = compute_candidates(state)
    assert too_slow not in flat
    assert in_range in flat


def test_compute_candidates_sorted_by_score_within_group():
    seed = _Song("seed", 128.0, "6d")
    # Both are "matching" type (6d); pick BPMs that differ in score
    best = _Song("best", 128.0, "6d")  # perfect BPM match → highest score
    worse = _Song("worse", 120.0, "6d")  # 8 BPM below → lower score
    state = _make_state(seed, [worse, best])
    grouped, _ = compute_candidates(state)
    group_dict = {label: songs for label, songs in grouped}
    songs = group_dict["matching"]
    assert songs.index(best) < songs.index(worse)


def test_compute_candidates_empty_pool():
    seed = _Song("seed", 128.0, "6d")
    state = _make_state(seed, [])
    _, flat = compute_candidates(state)
    assert flat == []


# ---------------------------------------------------------------------------
# select_candidate state transition
# ---------------------------------------------------------------------------


def test_select_candidate_updates_seed():
    seed = _Song("seed", 128.0, "6d")
    pick = _Song("p1", 128.0, "7d")  # boost
    state = _make_state(seed, [pick])
    new_state = select_candidate(state, pick)
    assert new_state.seed is pick


def test_select_candidate_appends_to_history():
    seed = _Song("seed", 128.0, "6d")
    pick = _Song("p1", 128.0, "7d")
    state = _make_state(seed, [pick])
    new_state = select_candidate(state, pick)
    assert pick in new_state.history


def test_select_candidate_adds_to_played_ids():
    seed = _Song("seed", 128.0, "6d")
    pick = _Song("p1", 128.0, "7d")
    state = _make_state(seed, [pick])
    new_state = select_candidate(state, pick)
    assert pick.id in new_state.played_ids


def test_select_candidate_recomputes_candidates():
    seed = _Song("seed", 128.0, "6d")
    pick = _Song("p1", 128.0, "7d")  # boost from 6d; becomes new seed
    next_candidate = _Song("n1", 128.0, "8d")  # boost from 7d
    state = _make_state(seed, [pick, next_candidate])
    new_state = select_candidate(state, pick)
    # After picking p1 (7d), next_candidate (8d) should be a boost candidate
    group_dict = {label: songs for label, songs in new_state.grouped}
    assert next_candidate in group_dict["boost"]


def test_select_candidate_cursor_resets():
    seed = _Song("seed", 128.0, "6d")
    pick = _Song("p1", 128.0, "7d")
    state = _make_state(seed, [pick])
    state.cursor = 0
    new_state = select_candidate(state, pick)
    assert new_state.cursor == 0


# ---------------------------------------------------------------------------
# undo
# ---------------------------------------------------------------------------


def test_undo_restores_previous_seed():
    seed = _Song("seed", 128.0, "6d")
    pick = _Song("p1", 128.0, "7d")
    state = _make_state(seed, [pick])
    state2 = select_candidate(state, pick)
    original_played = {seed.id}
    undone = undo(state2, original_played)
    assert undone.seed is seed


def test_undo_removes_last_history_entry():
    seed = _Song("seed", 128.0, "6d")
    pick = _Song("p1", 128.0, "7d")
    state = _make_state(seed, [pick])
    state2 = select_candidate(state, pick)
    undone = undo(state2, {seed.id})
    assert pick not in undone.history


def test_undo_restores_pick_as_candidate():
    seed = _Song("seed", 128.0, "6d")
    pick = _Song("p1", 128.0, "7d")
    state = _make_state(seed, [pick])
    state2 = select_candidate(state, pick)
    undone = undo(state2, set())
    assert pick in undone.flat


def test_undo_noop_when_only_seed():
    seed = _Song("seed", 128.0, "6d")
    state = _make_state(seed, [])
    result = undo(state, set())
    assert result.history == state.history


def test_undo_chain():
    seed = _Song("seed", 128.0, "6d")
    p1 = _Song("p1", 128.0, "7d")
    p2 = _Song("p2", 128.0, "8d")
    pool = [p1, p2]
    state = _make_state(seed, pool)
    state2 = select_candidate(state, p1)
    state3 = select_candidate(state2, p2)
    original = {seed.id}
    state_back1 = undo(state3, original)
    assert state_back1.seed is p1
    state_back2 = undo(state_back1, original)
    assert state_back2.seed is seed


# ---------------------------------------------------------------------------
# save_csv
# ---------------------------------------------------------------------------


def test_save_csv_columns(tmp_path):
    seed = _Song("seed", 128.0, "6d")
    pick = _Song("p1", 129.0, "7d")
    state = _make_state(seed, [pick])
    state2 = select_candidate(state, pick)
    out = tmp_path / "out.csv"
    save_csv(state2, out)
    rows = list(csv.DictReader(out.read_text().splitlines()))
    assert rows
    expected_cols = {
        "position",
        "apple_music_id",
        "artist",
        "name",
        "key",
        "bpm",
        "transition_type",
        "transition_score",
    }
    assert expected_cols == set(rows[0].keys())


def test_save_csv_history_order(tmp_path):
    seed = _Song("seed", 128.0, "6d")
    p1 = _Song("p1", 128.0, "7d")
    p2 = _Song("p2", 128.0, "8d")
    state = _make_state(seed, [p1, p2])
    state2 = select_candidate(state, p1)
    state3 = select_candidate(state2, p2)
    out = tmp_path / "out.csv"
    save_csv(state3, out)
    rows = list(csv.DictReader(out.read_text().splitlines()))
    ids = [r["apple_music_id"] for r in rows]
    assert ids == ["seed", "p1", "p2"]


def test_save_csv_transition_type_recorded(tmp_path):
    seed = _Song("seed", 128.0, "6d")
    p1 = _Song("p1", 128.0, "7d")  # boost from 6d→7d
    state = _make_state(seed, [p1])
    state2 = select_candidate(state, p1)
    out = tmp_path / "out.csv"
    save_csv(state2, out)
    rows = list(csv.DictReader(out.read_text().splitlines()))
    # second row is p1; transition from seed (6d) to p1 (7d) = boost
    assert rows[1]["transition_type"] == "boost"


def test_save_csv_empty_history(tmp_path):
    seed = _Song("seed", 128.0, "6d")
    state = _make_state(seed, [])
    out = tmp_path / "out.csv"
    save_csv(state, out)
    rows = list(csv.DictReader(out.read_text().splitlines()))
    # seed is in history[0], so one row
    assert len(rows) == 1
