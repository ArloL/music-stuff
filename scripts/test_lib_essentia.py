from pathlib import Path
from unittest.mock import patch

import pytest

from lib_essentia import (
    _location_to_path,
    _coerce,
    _normalise_bpm,
    consensus_bpm,
    consensus_key,
    _load_essentia_cache,
    _write_essentia_cache,
    ESSENTIA_PROFILES,
)


# --- _location_to_path ---

def test_location_to_path_decodes_file_url():
    assert _location_to_path("file:///Users/test/My%20Music/song.mp3") == Path("/Users/test/My Music/song.mp3")


def test_location_to_path_passes_through_plain_path():
    assert _location_to_path("/Users/test/song.mp3") == Path("/Users/test/song.mp3")


def test_location_to_path_returns_none_for_empty():
    assert _location_to_path("") is None
    assert _location_to_path(None) is None


# --- _coerce ---

def test_coerce_converts_numeric_strings_to_float():
    assert _coerce("3.14") == 3.14
    assert _coerce("42") == 42.0


def test_coerce_leaves_non_numeric_strings_unchanged():
    assert _coerce("Key 5d") == "Key 5d"
    assert _coerce("") == ""


# --- _normalise_bpm ---

def test_normalise_bpm_halves_above_range():
    assert _normalise_bpm(240.0) == 120.0
    assert _normalise_bpm(400.0) == 200.0  # 400 -> 200 (in range)


def test_normalise_bpm_doubles_below_range():
    assert _normalise_bpm(30.0) == 60.0   # one doubling into range
    assert _normalise_bpm(55.0) == 110.0


def test_normalise_bpm_leaves_in_range_untouched():
    assert _normalise_bpm(120.0) == 120.0
    assert _normalise_bpm(60.0) == 60.0
    assert _normalise_bpm(200.0) == 200.0


# --- consensus_bpm ---

def test_consensus_bpm_averages_when_estimates_agree():
    entry = {"bpm_rhythm": 120.0, "bpm_percival": 122.0}
    assert consensus_bpm(entry) == 121.0


def test_consensus_bpm_resolves_octave_error():
    """One estimator at half BPM — after normalisation both agree."""
    entry = {"bpm_rhythm": 120.0, "bpm_percival": 60.0}
    assert consensus_bpm(entry) == 120.0  # 60 normalises to 120


def test_consensus_bpm_prefers_in_range_estimator():
    entry = {"bpm_rhythm": 100.0, "bpm_percival": 220.0}
    assert consensus_bpm(entry) == 100.0  # rhythm is in range, percival is not

    entry = {"bpm_rhythm": 220.0, "bpm_percival": 100.0}
    assert consensus_bpm(entry) == 100.0  # percival is in range


def test_consensus_bpm_falls_back_when_one_is_zero():
    assert consensus_bpm({"bpm_rhythm": 130.0, "bpm_percival": 0.0}) == 130.0
    assert consensus_bpm({"bpm_rhythm": 0.0, "bpm_percival": 140.0}) == 140.0


def test_consensus_bpm_returns_zero_when_no_data():
    assert consensus_bpm({}) == 0.0
    assert consensus_bpm({"bpm_rhythm": 0.0, "bpm_percival": 0.0}) == 0.0


# --- consensus_key ---

def test_consensus_key_returns_unanimous_winner():
    entry = {f"{p}_key": "Key 5d" for p in ESSENTIA_PROFILES}
    entry.update({f"{p}_strength": 0.8 for p in ESSENTIA_PROFILES})
    assert consensus_key(entry) == "Key 5d"


def test_consensus_key_is_strength_weighted():
    """A single high-confidence profile can outweigh many low-confidence ones."""
    entry = {}
    for i, p in enumerate(ESSENTIA_PROFILES):
        if i == 0:
            entry[f"{p}_key"] = "Key 7d"
            entry[f"{p}_strength"] = 10.0
        else:
            entry[f"{p}_key"] = "Key 1m"
            entry[f"{p}_strength"] = 0.1
    assert consensus_key(entry) == "Key 7d"


def test_consensus_key_ignores_empty_keys():
    entry = {
        "edma_key": "", "edma_strength": 0.9,
        "edmm_key": "Key 3d", "edmm_strength": 0.5,
    }
    assert consensus_key(entry) == "Key 3d"


def test_consensus_key_empty_input():
    assert consensus_key({}) == ""


# --- cache I/O ---

def test_cache_round_trip_preserves_types(tmp_path):
    cache_path = tmp_path / "cache.csv"
    cache = {
        "ABC123": {"edma_key": "Key 5d", "edma_strength": 0.85, "bpm_rhythm": 120.5},
        "DEF456": {"edma_key": "Key 1m", "edma_strength": 0.72, "bpm_rhythm": 95.0},
    }

    with patch("lib_essentia.ESSENTIA_CACHE_PATH", cache_path):
        _write_essentia_cache(cache)
        loaded = _load_essentia_cache()

    assert set(loaded.keys()) == {"ABC123", "DEF456"}
    assert loaded["ABC123"]["edma_key"] == "Key 5d"
    assert loaded["ABC123"]["edma_strength"] == 0.85
    assert loaded["ABC123"]["bpm_rhythm"] == 120.5


def test_cache_writes_sorted_by_id(tmp_path):
    cache_path = tmp_path / "cache.csv"
    cache = {"ZZZ": {"bpm_rhythm": 100.0}, "AAA": {"bpm_rhythm": 200.0}}

    with patch("lib_essentia.ESSENTIA_CACHE_PATH", cache_path):
        _write_essentia_cache(cache)

    lines = cache_path.read_text().splitlines()
    assert "AAA" in lines[1]
    assert "ZZZ" in lines[2]


def test_load_cache_returns_empty_for_missing_file(tmp_path):
    with patch("lib_essentia.ESSENTIA_CACHE_PATH", tmp_path / "nonexistent.csv"):
        assert _load_essentia_cache() == {}
