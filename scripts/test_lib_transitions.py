import pandas as pd
import pytest
from lib_transitions import (
    calculate_transition_score,
    get_transition_type,
    validate_keys,
    ALLOWED_KEY_TRANSITIONS,
    TRANSITIONS_WEIGHTS,
)


# --- get_transition_type ---

def test_get_transition_type_all_types():
    """Verify one representative pair for each transition type."""
    assert get_transition_type({'key': 0}, {'key': 0}) == 'incompatible'
    assert get_transition_type({'key': 11}, {'key': 11}) == 'matching'
    assert get_transition_type({'key': 11}, {'key': 14}) == 'matching'  # relative key
    assert get_transition_type({'key': 11}, {'key': 13}) == 'boost'
    assert get_transition_type({'key': 11}, {'key': 5}) == 'boost boost'
    assert get_transition_type({'key': 11}, {'key': 15}) == 'boost boost boost'
    assert get_transition_type({'key': 11}, {'key': 9}) == 'drop'
    assert get_transition_type({'key': 11}, {'key': 17}) == 'drop drop'
    assert get_transition_type({'key': 11}, {'key': 7}) == 'drop drop drop'


def test_get_transition_type_minor_keys():
    assert get_transition_type({'key': 12}, {'key': 12}) == 'matching'
    assert get_transition_type({'key': 12}, {'key': 10}) == 'drop'


# --- calculate_transition_score ---

def test_score_perfect_match():
    """Same key and BPM = max score (100)."""
    assert calculate_transition_score({'key': 11, 'bpm': 120}, {'key': 11, 'bpm': 120}) == 100


def test_score_zero_when_bpm_exceeds_tolerance():
    assert calculate_transition_score({'key': 11, 'bpm': 100}, {'key': 11, 'bpm': 121}) == 0


def test_score_zero_for_incompatible_keys():
    assert calculate_transition_score({'key': 0, 'bpm': 120}, {'key': 0, 'bpm': 120}) == 0


def test_score_bpm_up_vs_down_asymmetry():
    """Going up by N BPM is penalized less than going down by N (for small drops)."""
    base = {'key': 11, 'bpm': 120}
    score_up = calculate_transition_score(base, {'key': 11, 'bpm': 122})
    score_down = calculate_transition_score(base, {'key': 11, 'bpm': 118})
    assert score_up > score_down  # small drops are penalized more heavily


def test_score_small_drop_penalized_more_than_large_drop():
    """The code penalizes 0-2 BPM drops (×5) more than >2 BPM drops (×1)."""
    base = {'key': 11, 'bpm': 120}
    # 2 BPM drop: bpm_score = 100 - (2*5) = 90
    score_2 = calculate_transition_score(base, {'key': 11, 'bpm': 118})
    # 5 BPM drop: bpm_score = 100 - 5 = 95
    score_5 = calculate_transition_score(base, {'key': 11, 'bpm': 115})
    assert score_5 > score_2


def test_score_weights_bpm_60_key_40():
    """Score = bpm_score * 0.6 + key_score * 0.4."""
    # BPM +5 (up): bpm_score = 95, key = matching (100)
    score = calculate_transition_score({'key': 11, 'bpm': 120}, {'key': 11, 'bpm': 125})
    assert score == pytest.approx(95 * 0.6 + 100 * 0.4)


def test_score_custom_tolerance():
    assert calculate_transition_score({'key': 11, 'bpm': 100}, {'key': 11, 'bpm': 125}, bpm_tolerance=30) > 0


def test_score_drop_drop_drop_matching_bpm():
    assert calculate_transition_score({'key': 11, 'bpm': 120}, {'key': 7, 'bpm': 120}) == pytest.approx(
        100 * 0.6 + 30 * 0.4  # 72
    )


# --- validate_keys ---

def test_validate_keys_all_valid():
    df = pd.DataFrame({"key": [1, 3, 5, 11, 24]})
    assert validate_keys(df) is True


def test_validate_keys_rejects_invalid(capsys):
    df = pd.DataFrame({"key": [1, 0, 99]})
    assert validate_keys(df) is False
    assert "invalid keys" in capsys.readouterr().out.lower()


# --- ALLOWED_KEY_TRANSITIONS structure ---

def test_all_transition_types_have_weights():
    for t in ALLOWED_KEY_TRANSITIONS:
        assert t in TRANSITIONS_WEIGHTS


def test_every_key_1_to_24_is_a_source_in_all_transition_types():
    expected = set(range(1, 25))
    for name, transitions in ALLOWED_KEY_TRANSITIONS.items():
        assert set(transitions.keys()) == expected, f"{name} missing keys"
