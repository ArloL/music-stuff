import pandas as pd
import pytest
from music_stuff.lib.lib_transitions import (
    calculate_transition_score,
    get_transition_type,
    validate_keys,
    ALLOWED_KEY_TRANSITIONS,
    REVERSE_KEY_TRANSITIONS,
    TRANSITIONS_WEIGHTS,
)


# --- get_transition_type ---

def test_get_transition_type_all_types():
    """Verify one representative pair for each transition type."""
    assert get_transition_type({'key': "0d"}, {'key': "0d"}) == 'incompatible'
    assert get_transition_type({'key': "6d"}, {'key': "6d"}) == 'matching'
    assert get_transition_type({'key': "6d"}, {'key': "7m"}) == 'matching'  # relative key
    assert get_transition_type({'key': "6d"}, {'key': "7d"}) == 'boost'
    assert get_transition_type({'key': "6d"}, {'key': "3d"}) == 'boost boost'
    assert get_transition_type({'key': "6d"}, {'key': "8d"}) == 'boost boost boost'
    assert get_transition_type({'key': "6d"}, {'key': "5d"}) == 'drop'
    assert get_transition_type({'key': "6d"}, {'key': "9d"}) == 'drop drop'
    assert get_transition_type({'key': "6d"}, {'key': "4d"}) == 'drop drop drop'


def test_get_transition_type_minor_keys():
    assert get_transition_type({'key': "6m"}, {'key': "6m"}) == 'matching'
    assert get_transition_type({'key': "6m"}, {'key': "5m"}) == 'drop'


# --- calculate_transition_score ---

def test_score_perfect_match():
    """Same key and BPM = max score (100)."""
    assert calculate_transition_score({'key': "6d", 'bpm': 120}, {'key': "6d", 'bpm': 120}) == 100


def test_score_zero_when_bpm_exceeds_tolerance():
    assert calculate_transition_score({'key': "6d", 'bpm': 100}, {'key': "6d", 'bpm': 121}) == 0


def test_score_zero_for_incompatible_keys():
    assert calculate_transition_score({'key': "0d", 'bpm': 120}, {'key': "0d", 'bpm': 120}) == 0


def test_score_bpm_up_vs_down_asymmetry():
    """Going up by N BPM is penalized less than going down by N (for small drops)."""
    base = {'key': "6d", 'bpm': 120}
    score_up = calculate_transition_score(base, {'key': "6d", 'bpm': 122})
    score_down = calculate_transition_score(base, {'key': "6d", 'bpm': 118})
    assert score_up > score_down  # small drops are penalized more heavily


def test_score_small_drop_penalized_more_than_large_drop():
    """The code penalizes 0-2 BPM drops (×5) more than >2 BPM drops (×1)."""
    base = {'key': "6d", 'bpm': 120}
    # 2 BPM drop: bpm_score = 100 - (2*5) = 90
    score_2 = calculate_transition_score(base, {'key': "6d", 'bpm': 118})
    # 5 BPM drop: bpm_score = 100 - 5 = 95
    score_5 = calculate_transition_score(base, {'key': "6d", 'bpm': 115})
    assert score_5 > score_2


def test_score_weights_bpm_60_key_40():
    """Score = bpm_score * 0.6 + key_score * 0.4."""
    # BPM +5 (up): bpm_score = 95, key = matching (100)
    score = calculate_transition_score({'key': "6d", 'bpm': 120}, {'key': "6d", 'bpm': 125})
    assert score == pytest.approx(95 * 0.6 + 100 * 0.4)


def test_score_custom_tolerance():
    assert calculate_transition_score({'key': "6d", 'bpm': 100}, {'key': "6d", 'bpm': 125}, bpm_tolerance=30) > 0


def test_score_drop_drop_drop_matching_bpm():
    assert calculate_transition_score({'key': "6d", 'bpm': 120}, {'key': "4d", 'bpm': 120}) == pytest.approx(
        100 * 0.6 + 30 * 0.4  # 72
    )


# --- validate_keys ---

def test_validate_keys_all_valid():
    df = pd.DataFrame({"key": ["1d", "2d", "3d", "6d", "12m"]})
    assert validate_keys(df) is True


def test_validate_keys_rejects_invalid(capsys):
    df = pd.DataFrame({"key": ["1d", "0d", "99x"]})
    assert validate_keys(df) is False
    assert "invalid keys" in capsys.readouterr().out.lower()


# --- ALLOWED_KEY_TRANSITIONS structure ---

def test_all_transition_types_have_weights():
    for t in ALLOWED_KEY_TRANSITIONS:
        assert t in TRANSITIONS_WEIGHTS


def test_every_open_key_is_a_source_in_all_transition_types():
    major_keys = {f"{n}d" for n in range(1, 13)}
    minor_keys = {f"{n}m" for n in range(1, 13)}
    expected = major_keys | minor_keys
    for name, transitions in ALLOWED_KEY_TRANSITIONS.items():
        assert set(transitions.keys()) == expected, f"{name} missing keys"


# --- REVERSE_KEY_TRANSITIONS ---

def test_reverse_transitions_has_same_types():
    assert set(REVERSE_KEY_TRANSITIONS.keys()) == set(ALLOWED_KEY_TRANSITIONS.keys())


def test_reverse_transitions_inverts_forward():
    """If forward says 6d→7d (boost), then reverse boost should map 7d→[..., 6d, ...]."""
    assert "6d" in REVERSE_KEY_TRANSITIONS["boost"]["7d"]


def test_reverse_transitions_covers_all_target_keys():
    """Every key that appears as a target in forward should be a source in reverse."""
    for ttype, forward in ALLOWED_KEY_TRANSITIONS.items():
        all_targets = {t for targets in forward.values() for t in targets}
        assert all_targets <= set(REVERSE_KEY_TRANSITIONS[ttype].keys()), f"{ttype} missing reverse keys"
