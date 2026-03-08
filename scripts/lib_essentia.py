import csv
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname


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
            int(row["apple_music_id"]): {k: _coerce(v) for k, v in row.items() if k != "apple_music_id"}
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
    """Analyse a single track: key profiles and/or BPM. Loads audio once."""
    try:
        import essentia.standard as es  # type: ignore
    except ImportError:
        return {}

    path = _location_to_path(location)
    if path is None or not path.exists():
        return {}

    try:
        audio = es.MonoLoader(filename=str(path))()
    except Exception:
        return {}

    result = {}
    for profile in profiles:
        try:
            key, scale, strength = es.KeyExtractor(profileType=profile)(audio)
            mapping = _ESSENTIA_MAJOR_TO_OPEN_KEY if scale == "major" else _ESSENTIA_MINOR_TO_OPEN_KEY
            open_key = mapping.get(key, "")
            result[f"{profile}_key"] = f"Key {open_key}" if open_key else ""
            result[f"{profile}_strength"] = round(float(strength), 4)
        except Exception:
            result[f"{profile}_key"] = ""
            result[f"{profile}_strength"] = 0.0

    if do_bpm:
        try:
            bpm, _, _, _, _ = es.RhythmExtractor2013(method="multifeature")(audio)
            result["bpm"] = round(float(bpm), 2)
        except Exception:
            result["bpm"] = ""

    return result


def analyse(tracks: list[dict]) -> dict[int, dict]:
    """Load the essentia cache, run parallel key+BPM analysis for missing data, save and return."""
    cache = _load_essentia_cache()
    print(f"  Essentia cache: {len(cache)} entries loaded from {ESSENTIA_CACHE_PATH.name}")
    done = 0
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = {}
        for track in tracks:
            entry = cache.get(track["id"], {})
            missing_profiles = [p for p in ESSENTIA_PROFILES if f"{p}_key" not in entry]
            missing_bpm = "bpm" not in entry
            if missing_profiles or missing_bpm:
                futures[executor.submit(_detect_essentia, track["location"], missing_profiles, missing_bpm)] = track["id"]
        for future in as_completed(futures):
            pid = futures[future]
            cache.setdefault(pid, {}).update(future.result())
            done += 1
            print(f"  Analysing [{done}/{len(futures)}]", end="\r")
    print()
    _write_essentia_cache(cache)
    return cache


def consensus_key(entry: dict) -> str:
    """Strength-weighted majority vote across profiles. Returns the winning open key."""
    votes: dict[str, float] = {}
    for p in ESSENTIA_PROFILES:
        open_key = entry.get(f"{p}_key", "")
        strength = entry.get(f"{p}_strength", 0.0)
        if open_key:
            votes[open_key] = votes.get(open_key, 0.0) + strength
    return max(votes, key=lambda k: votes[k]) if votes else ""
