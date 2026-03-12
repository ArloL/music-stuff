from music_stuff.lib.lib_consensus import consensus_key, essentia_profile_keys
from music_stuff.lib.lib_essentia import ESSENTIA_PROFILES


# --- essentia_profile_keys ---

def test_essentia_profile_keys_extracts_votes():
    entry = {
        "edma_key": "Key 5d", "edma_strength": 0.85,
        "edmm_key": "Key 5d", "edmm_strength": 0.70,
        "bgate_key": "Key 1m", "bgate_strength": 0.60,
    }
    result = essentia_profile_keys(entry, ["edma", "edmm", "bgate"])
    assert result == {"Key 5d": 0.85 + 0.70, "Key 1m": 0.60}


def test_essentia_profile_keys_skips_empty_keys():
    entry = {"edma_key": "", "edma_strength": 0.9, "edmm_key": "Key 3d", "edmm_strength": 0.5}
    result = essentia_profile_keys(entry, ["edma", "edmm"])
    assert result == {"Key 3d": 0.5}


def test_essentia_profile_keys_empty_entry():
    assert essentia_profile_keys({}, ESSENTIA_PROFILES) == {}


# --- consensus_key: Essentia only ---

def test_unanimous_essentia_profiles():
    keys = {f"{p}_key": "Key 5d" for p in ESSENTIA_PROFILES}
    keys.update({f"{p}_strength": 0.8 for p in ESSENTIA_PROFILES})
    profile_keys = essentia_profile_keys(keys, ESSENTIA_PROFILES)
    assert consensus_key(essentia_keys=profile_keys) == "Key 5d"


def test_strength_weighted_voting():
    """A single high-confidence profile can outweigh many low-confidence ones."""
    entry = {}
    for i, p in enumerate(ESSENTIA_PROFILES):
        if i == 0:
            entry[f"{p}_key"] = "Key 7d"
            entry[f"{p}_strength"] = 10.0
        else:
            entry[f"{p}_key"] = "Key 1m"
            entry[f"{p}_strength"] = 0.1
    profile_keys = essentia_profile_keys(entry, ESSENTIA_PROFILES)
    assert consensus_key(essentia_keys=profile_keys) == "Key 7d"


def test_empty_essentia_keys_ignored():
    entry = {"edma_key": "", "edma_strength": 0.9, "edmm_key": "Key 3d", "edmm_strength": 0.5}
    profile_keys = essentia_profile_keys(entry, ["edma", "edmm"])
    assert consensus_key(essentia_keys=profile_keys) == "Key 3d"


def test_empty_entry_returns_empty():
    assert consensus_key() == ""
    assert consensus_key(essentia_keys={}) == ""


# --- consensus_key: external keys ---

def test_external_keys_reinforce_essentia_majority():
    """djay and beaTunes agree with the Essentia majority — same winner."""
    entry = {}
    for p in ESSENTIA_PROFILES:
        entry[f"{p}_key"] = "Key 5d"
        entry[f"{p}_strength"] = 0.5
    profile_keys = essentia_profile_keys(entry, ESSENTIA_PROFILES)
    result = consensus_key(
        djay_key="Key 5d", beatunes_key="Key 5d", essentia_keys=profile_keys,
    )
    assert result == "Key 5d"


def test_external_keys_swing_weak_essentia_split():
    """Essentia is split; djay and beaTunes tip the balance."""
    entry = {
        "edma_key": "Key 5d", "edma_strength": 0.5,
        "edmm_key": "Key 5d", "edmm_strength": 0.5,
        "bgate_key": "Key 1m", "bgate_strength": 0.5,
        "braw_key": "Key 1m", "braw_strength": 0.5,
    }
    profile_keys = essentia_profile_keys(entry, ["edma", "edmm", "bgate", "braw"])
    # Essentia is tied 1.0 vs 1.0; external keys break the tie
    result = consensus_key(
        djay_key="Key 1m", beatunes_key="Key 1m", essentia_keys=profile_keys,
    )
    assert result == "Key 1m"


def test_empty_external_keys_ignored():
    entry = {f"{p}_key": "Key 5d" for p in ESSENTIA_PROFILES}
    entry.update({f"{p}_strength": 0.8 for p in ESSENTIA_PROFILES})
    profile_keys = essentia_profile_keys(entry, ESSENTIA_PROFILES)
    result = consensus_key(djay_key="", beatunes_key="", essentia_keys=profile_keys)
    assert result == "Key 5d"


def test_only_external_keys_no_essentia():
    assert consensus_key(djay_key="Key 3d", beatunes_key="Key 3d") == "Key 3d"


def test_single_external_key_only():
    assert consensus_key(djay_key="Key 8m") == "Key 8m"
    assert consensus_key(beatunes_key="Key 12d") == "Key 12d"


def test_external_keys_disagree():
    """When only external keys are present and they disagree, either wins (both weight 1.0)."""
    result = consensus_key(djay_key="Key 3d", beatunes_key="Key 8m")
    assert result in ("Key 3d", "Key 8m")
