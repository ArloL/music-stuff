import pytest
from lib_transitions import calculate_transition_score, get_transition_type

def test_get_transition_type_incompatible():
    assert get_transition_type({'key':0}, {'key': 0}) == 'incompatible'

def test_get_transition_type_drop_drop_drop():
    assert get_transition_type({'key':11}, {'key': 7}) == 'drop drop drop'

def test_get_transition_type_drop_drop():
    assert get_transition_type({'key':11}, {'key': 17}) == 'drop drop'

def test_get_transition_type_drop():
    assert get_transition_type({'key':11}, {'key': 9}) == 'drop'

def test_calculate_transition_score_matching_key_and_bpm():
    assert calculate_transition_score({'key':11, 'bpm': 120}, {'key': 11, 'bpm': 120}) == 100

def test_calculate_transition_score_matching_bpm_drop_drop_drop():
    assert calculate_transition_score({'key':11, 'bpm': 120}, {'key': 7, 'bpm': 120}) == 72
