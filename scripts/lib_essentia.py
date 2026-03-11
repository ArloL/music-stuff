import csv
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

import essentia.standard as es


ESSENTIA_CACHE_PATH = Path(__file__).parent / "lib_essentia_cache.csv"

ESSENTIA_PROFILES = ["edma", "edmm", "bgate", "braw", "shaath", "temperley", "noland"]

# pip install essentia  (or: brew install essentia on macOS)
# Maps essentia key names to Open Key numbers for major (d) and minor (m).
# Includes both sharp and flat spellings since KeyExtractor may return either.
_ESSENTIA_MAJOR_TO_OPEN_KEY: dict[str, str] = {
    "C": "1d",  "G": "2d",  "D": "3d",   "A": "4d",
    "E": "5d",  "B": "6d",  "F#": "7d",  "Gb": "7d",
    "C#": "8d", "Db": "8d", "G#": "9d",  "Ab": "9d",
    "D#": "10d","Eb": "10d","A#": "11d", "Bb": "11d",
    "F": "12d",
}
_ESSENTIA_MINOR_TO_OPEN_KEY: dict[str, str] = {
    "A": "1m",  "E": "2m",  "B": "3m",   "F#": "4m",  "Gb": "4m",
    "C#": "5m", "Db": "5m", "G#": "6m",  "Ab": "6m",
    "D#": "7m", "Eb": "7m", "A#": "8m",  "Bb": "8m",
    "F": "9m",  "C": "10m", "G": "11m",  "D": "12m",
}


def _location_to_path(location: str) -> Path | None:
    if not location:
        return None
    if location.startswith("file://"):
        return Path(url2pathname(urlparse(location).path))
    return Path(location)


def _coerce(v: str):
    try:
        return float(v)
    except (ValueError, TypeError):
        return v


def _load_essentia_cache() -> dict[int, dict]:
    """Load apple_music_id -> flat dict of {bpm, profile_key, profile_strength, ...}."""
    if not ESSENTIA_CACHE_PATH.exists():
        return {}
    with open(ESSENTIA_CACHE_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "apple_music_id" not in reader.fieldnames:
            return {}
        return {
            row["apple_music_id"]: {k: _coerce(v) for k, v in row.items() if k != "apple_music_id"}
            for row in reader
        }


def _write_essentia_cache(cache: dict[int, dict]) -> None:
    """Write the cache CSV sorted by apple_music_id."""
    fieldnames = ["apple_music_id"]
    seen: set[str] = set()
    for entry in cache.values():
        for k in entry:
            if k not in seen:
                fieldnames.append(k)
                seen.add(k)
    with open(ESSENTIA_CACHE_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for pid in sorted(cache):
            writer.writerow({"apple_music_id": pid, **cache[pid]})


def _detect_essentia(location: str, profiles: list[str], do_bpm: bool) -> dict:
    """Analyse a single song: key profiles and/or BPM. Loads audio once."""
    path = _location_to_path(location)
    if path is None:
        raise ValueError(f"No location for song: {location!r}")
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")

    audio = es.MonoLoader(filename=str(path))()

    result = {}
    for profile in profiles:
        key, scale, strength = es.KeyExtractor(profileType=profile)(audio)
        mapping = _ESSENTIA_MAJOR_TO_OPEN_KEY if scale == "major" else _ESSENTIA_MINOR_TO_OPEN_KEY
        open_key = mapping.get(key, "")
        result[f"{profile}_key"] = f"Key {open_key}" if open_key else ""
        result[f"{profile}_strength"] = round(float(strength), 4)

    if do_bpm:
        bpm_r, _, confidence_r, _, _ = es.RhythmExtractor2013(method="multifeature")(audio)
        bpm_p = es.PercivalBpmEstimator()(audio)
        result["bpm_rhythm"] = round(float(bpm_r), 2)
        result["bpm_rhythm_confidence"] = round(float(confidence_r), 4)
        result["bpm_percival"] = round(float(bpm_p), 2)

    return result


def analyse(songs: list[dict]) -> dict[int, dict]:
    """Load the essentia cache, run parallel key+BPM analysis for missing data, save and return."""
    cache = _load_essentia_cache()
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = {}
        for song in songs:
            pid = song["persistentID"]
            entry = cache.get(pid, {})
            missing_profiles = [p for p in ESSENTIA_PROFILES if f"{p}_key" not in entry]
            missing_bpm = "bpm_rhythm" not in entry or "bpm_rhythm_confidence" not in entry or "bpm_percival" not in entry
            if missing_profiles or missing_bpm:
                futures[executor.submit(_detect_essentia, song["location"], missing_profiles, missing_bpm)] = pid
        done = 0
        for future in as_completed(futures):
            pid = futures[future]
            cache.setdefault(pid, {}).update(future.result())
            done += 1
            print(f"  Analysing [{done}/{len(futures)}]", end="\r")
            _write_essentia_cache(cache)
        if futures:
            print()
    return cache


_BPM_RANGE = (60.0, 200.0)


def _normalise_bpm(bpm: float) -> float:
    """Fold a BPM value into _BPM_RANGE by halving or doubling."""
    lo, hi = _BPM_RANGE
    while bpm > hi:
        bpm /= 2
    while bpm < lo:
        bpm *= 2
    return bpm


def consensus_bpm(entry: dict) -> float:
    """Consensus BPM from RhythmExtractor2013 and PercivalBpmEstimator.

    Both estimates are normalised to _BPM_RANGE to resolve octave errors.
    If they agree within 5 % after normalisation, they are averaged; otherwise
    the estimate already in range is preferred, falling back to rhythm.
    """
    r = float(entry.get("bpm_rhythm") or 0.0)
    p = float(entry.get("bpm_percival") or 0.0)
    if not r and not p:
        return 0.0
    if not r:
        return round(_normalise_bpm(p), 2)
    if not p:
        return round(_normalise_bpm(r), 2)

    rn, pn = _normalise_bpm(r), _normalise_bpm(p)
    mid = (rn + pn) / 2
    if abs(rn - pn) / mid < 0.05:
        return round(mid, 2)

    r_in = _BPM_RANGE[0] <= r <= _BPM_RANGE[1]
    p_in = _BPM_RANGE[0] <= p <= _BPM_RANGE[1]
    if r_in and not p_in:
        return round(r, 2)
    if p_in and not r_in:
        return round(p, 2)
    return round(rn, 2)  # both needed folding — prefer rhythm after normalisation


def consensus_key(entry: dict) -> str:
    """Strength-weighted majority vote across profiles. Returns the winning open key."""
    votes: dict[str, float] = {}
    for p in ESSENTIA_PROFILES:
        open_key = entry.get(f"{p}_key", "")
        strength = entry.get(f"{p}_strength", 0.0)
        if open_key:
            votes[open_key] = votes.get(open_key, 0.0) + strength
    return max(votes, key=lambda k: votes[k]) if votes else ""
