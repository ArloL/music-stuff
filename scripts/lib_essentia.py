import csv
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname


KEY_CACHE_PATH = Path(__file__).parent / "essentia-key-cache.csv"

ESSENTIA_PROFILES = ["edma", "edmm", "bgate", "braw", "shaath", "temperley", "noland"]

# profile results type: profile -> (open_key, strength)
KeyProfileResults = dict[str, tuple[str, float]]

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


def load_key_cache() -> dict[int, KeyProfileResults]:
    """Load apple_music_id -> {profile: (open_key, strength)} from the cache CSV.
    Loads all profile columns present in the file, regardless of current ESSENTIA_PROFILES."""
    if not KEY_CACHE_PATH.exists():
        return {}
    with open(KEY_CACHE_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "apple_music_id" not in reader.fieldnames:
            return {}
        all_profiles = [
            col[:-4] for col in reader.fieldnames if col.endswith("_key") and col != "apple_music_id"
        ]
        result: dict[int, KeyProfileResults] = {}
        for row in reader:
            pid = int(row["apple_music_id"])
            result[pid] = {
                p: (row[f"{p}_key"], float(row.get(f"{p}_strength") or 0.0))
                for p in all_profiles
            }
        return result


def write_key_cache(cache: dict[int, KeyProfileResults]) -> None:
    """Write the cache CSV sorted by apple_music_id, preserving all profiles in the data."""
    all_profiles: list[str] = []
    seen: set[str] = set()
    for profile_results in cache.values():
        for p in profile_results:
            if p not in seen:
                all_profiles.append(p)
                seen.add(p)
    fieldnames = ["apple_music_id"] + [f"{p}_{s}" for p in all_profiles for s in ("key", "strength")]
    with open(KEY_CACHE_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for pid in sorted(cache):
            row: dict = {"apple_music_id": pid}
            for p in all_profiles:
                open_key, strength = cache[pid].get(p, ("", 0.0))
                row[f"{p}_key"] = open_key
                row[f"{p}_strength"] = strength
            writer.writerow(row)


def detect_key_essentia(location: str, profiles: list[str]) -> KeyProfileResults:
    """
    Detect musical key using the given essentia KeyExtractor profiles.
    Returns dict mapping profile name -> (open_key, strength).
    """
    if not profiles:
        return {}
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

    results: KeyProfileResults = {}
    for profile in profiles:
        try:
            key, scale, strength = es.KeyExtractor(profileType=profile)(audio)
            mapping = _ESSENTIA_MAJOR_TO_OPEN_KEY if scale == "major" else _ESSENTIA_MINOR_TO_OPEN_KEY
            open_key = mapping.get(key, "")
            results[profile] = (f"Key {open_key}" if open_key else "", round(float(strength), 4))
        except Exception:
            results[profile] = ("", 0.0)
    return results


def analyse_keys(music_meta: dict) -> dict[int, KeyProfileResults]:
    """Load the key cache, run parallel essentia analysis for missing profiles, save and return the updated cache."""
    key_cache = load_key_cache()
    print(f"  Key cache: {len(key_cache)} entries loaded from {KEY_CACHE_PATH.name}")
    done = 0
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = {
            executor.submit(detect_key_essentia, meta["location"], [p for p in ESSENTIA_PROFILES if p not in key_cache.get(pid, {})]): pid
            for pid, meta in music_meta.items()
        }
        for future in as_completed(futures):
            pid = futures[future]
            key_cache.setdefault(pid, {}).update(future.result())
            done += 1
            print(f"  Analysing keys [{done}/{len(futures)}]", end="\r")
    print()
    write_key_cache(key_cache)
    return key_cache


def consensus_key(profile_results: KeyProfileResults) -> str:
    """Strength-weighted majority vote across profiles. Returns the winning open key."""
    votes: dict[str, float] = {}
    for open_key, strength in profile_results.values():
        if open_key:
            votes[open_key] = votes.get(open_key, 0.0) + strength
    return max(votes, key=lambda k: votes[k]) if votes else ""
