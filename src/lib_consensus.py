"""Consensus key from multiple data sources (Essentia profiles, djay, beaTunes)."""


def essentia_profile_keys(entry: dict, profiles: list[str]) -> dict[str, float]:
    """Extract {open_key: strength} votes from an Essentia cache entry."""
    votes: dict[str, float] = {}
    for p in profiles:
        open_key = entry.get(f"{p}_key", "")
        strength = entry.get(f"{p}_strength", 0.0)
        if open_key:
            votes[open_key] = votes.get(open_key, 0.0) + float(strength)
    return votes


def consensus_key(
    *,
    djay_key: str = "",
    beatunes_key: str = "",
    essentia_keys: dict[str, float] | None = None,
) -> str:
    """Strength-weighted majority vote across all key sources.

    Essentia profiles vote with their individual strength values.
    djay and beaTunes each vote with a fixed weight of 1.0.
    Returns the key with the highest total weight, or "" if no data.
    """
    votes: dict[str, float] = {}
    if essentia_keys:
        for key, strength in essentia_keys.items():
            if key:
                votes[key] = votes.get(key, 0.0) + strength
    if djay_key:
        votes[djay_key] = votes.get(djay_key, 0.0) + 1.0
    if beatunes_key:
        votes[beatunes_key] = votes.get(beatunes_key, 0.0) + 1.0
    return max(votes, key=lambda k: votes[k]) if votes else ""
