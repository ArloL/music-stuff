from collections import defaultdict

ALLOWED_KEY_TRANSITIONS = {
    "drop drop drop": {
        "6d": {"4d"},
        "7d": {"5d"},
        "8d": {"6d"},
        "9d": {"7d"},
        "10d": {"8d"},
        "11d": {"9d"},
        "12d": {"10d"},
        "1d": {"11d"},
        "2d": {"12d"},
        "3d": {"1d"},
        "4d": {"2d"},
        "5d": {"3d"},
        "6m": {"4m"},
        "7m": {"5m"},
        "8m": {"6m"},
        "9m": {"7m"},
        "10m": {"8m"},
        "11m": {"9m"},
        "12m": {"10m"},
        "1m": {"11m"},
        "2m": {"12m"},
        "3m": {"1m"},
        "4m": {"2m"},
        "5m": {"3m"},
    },
    "drop drop": {
        "6d": {"9d"},
        "7d": {"10d"},
        "8d": {"11d"},
        "9d": {"12d"},
        "10d": {"1d"},
        "11d": {"2d"},
        "12d": {"3d"},
        "1d": {"4d"},
        "2d": {"5d"},
        "3d": {"6d"},
        "4d": {"7d"},
        "5d": {"8d"},
        "6m": {"9m"},
        "7m": {"10m"},
        "8m": {"11m"},
        "9m": {"12m"},
        "10m": {"1m"},
        "11m": {"2m"},
        "12m": {"3m"},
        "1m": {"4m"},
        "2m": {"5m"},
        "3m": {"6m"},
        "4m": {"7m"},
        "5m": {"8m"},
    },
    "drop": {
        "6d": {"6m", "5d"},
        "7d": {"7m", "6d"},
        "8d": {"8m", "7d"},
        "9d": {"9m", "8d"},
        "10d": {"10m", "9d"},
        "11d": {"11m", "10d"},
        "12d": {"12m", "11d"},
        "1d": {"1m", "12d"},
        "2d": {"2m", "1d"},
        "3d": {"3m", "2d"},
        "4d": {"4m", "3d"},
        "5d": {"5m", "4d"},
        "6m": {"5m"},
        "7m": {"6m"},
        "8m": {"7m"},
        "9m": {"8m"},
        "10m": {"9m"},
        "11m": {"10m"},
        "12m": {"11m"},
        "1m": {"12m"},
        "2m": {"1m"},
        "3m": {"2m"},
        "4m": {"3m"},
        "5m": {"4m"},
    },
    "matching": {
        "6d": {"6d", "7m"},
        "7d": {"7d", "8m"},
        "8d": {"8d", "9m"},
        "9d": {"9d", "10m"},
        "10d": {"10d", "11m"},
        "11d": {"11d", "12m"},
        "12d": {"12d", "1m"},
        "1d": {"1d", "2m"},
        "2d": {"2d", "3m"},
        "3d": {"3d", "4m"},
        "4d": {"4d", "5m"},
        "5d": {"5d", "6m"},
        "6m": {"6m", "5d"},
        "7m": {"7m", "6d"},
        "8m": {"8m", "7d"},
        "9m": {"9m", "8d"},
        "10m": {"10m", "9d"},
        "11m": {"11m", "10d"},
        "12m": {"12m", "11d"},
        "1m": {"1m", "12d"},
        "2m": {"2m", "1d"},
        "3m": {"3m", "2d"},
        "4m": {"4m", "3d"},
        "5m": {"5m", "4d"},
    },
    "boost": {
        "6d": {"7d"},
        "7d": {"8d"},
        "8d": {"9d"},
        "9d": {"10d"},
        "10d": {"11d"},
        "11d": {"12d"},
        "12d": {"1d"},
        "1d": {"2d"},
        "2d": {"3d"},
        "3d": {"4d"},
        "4d": {"5d"},
        "5d": {"6d"},
        "6m": {"6d", "7m"},
        "7m": {"7d", "8m"},
        "8m": {"8d", "9m"},
        "9m": {"9d", "10m"},
        "10m": {"10d", "11m"},
        "11m": {"11d", "12m"},
        "12m": {"12d", "1m"},
        "1m": {"1d", "2m"},
        "2m": {"2d", "3m"},
        "3m": {"3d", "4m"},
        "4m": {"4d", "5m"},
        "5m": {"5d", "6m"},
    },
    "boost boost": {
        "6d": {"3d"},
        "7d": {"4d"},
        "8d": {"5d"},
        "9d": {"6d"},
        "10d": {"7d"},
        "11d": {"8d"},
        "12d": {"9d"},
        "1d": {"10d"},
        "2d": {"11d"},
        "3d": {"12d"},
        "4d": {"1d"},
        "5d": {"2d"},
        "6m": {"3m"},
        "7m": {"4m"},
        "8m": {"5m"},
        "9m": {"6m"},
        "10m": {"7m"},
        "11m": {"8m"},
        "12m": {"9m"},
        "1m": {"10m"},
        "2m": {"11m"},
        "3m": {"12m"},
        "4m": {"1m"},
        "5m": {"2m"},
    },
    "boost boost boost": {
        "6d": {"8d", "1d"},
        "7d": {"9d", "2d"},
        "8d": {"10d", "3d"},
        "9d": {"11d", "4d"},
        "10d": {"12d", "5d"},
        "11d": {"1d", "6d"},
        "12d": {"2d", "7d"},
        "1d": {"3d", "8d"},
        "2d": {"4d", "9d"},
        "3d": {"5d", "10d"},
        "4d": {"6d", "11d"},
        "5d": {"7d", "12d"},
        "6m": {"8m", "1m"},
        "7m": {"9m", "2m"},
        "8m": {"10m", "3m"},
        "9m": {"11m", "4m"},
        "10m": {"12m", "5m"},
        "11m": {"1m", "6m"},
        "12m": {"2m", "7m"},
        "1m": {"3m", "8m"},
        "2m": {"4m", "9m"},
        "3m": {"5m", "10m"},
        "4m": {"6m", "11m"},
        "5m": {"7m", "12m"},
    },
}

TRANSITIONS_WEIGHTS = {
    "matching": 100,  # Perfect harmonic match
    "boost": 95,  # Good energy increase
    "boost boost": 85,  # Moderate energy jump
    "boost boost boost": 50,  # Large energy jump
    "drop": 80,  # Good for breakdowns
    "drop drop": 40,  # Moderate energy drop
    "drop drop drop": 30,  # Large energy drop
}


def calculate_transition_score(song1, song2, bpm_tolerance=20):
    """Calculate a weighted score for the transition between two songs"""

    bpm_diff = song2["bpm"] - song1["bpm"]
    abs_bpm_diff = abs(bpm_diff)

    if abs_bpm_diff > bpm_tolerance:
        return 0

    if abs_bpm_diff == 0:
        # perfect match
        bpm_score = 100
    elif bpm_diff > 0:
        # going up; slight penalty
        bpm_score = 100 - abs_bpm_diff
    elif bpm_diff < -2:
        # going down a little, slight penalty
        bpm_score = 100 - abs_bpm_diff
    else:
        # going down a lot, larger penalty
        bpm_score = 100 - (abs_bpm_diff * 5)

    transition_type = get_transition_type(song1, song2)
    # No valid key transition found
    if transition_type == "incompatible":
        return 0
    key_score = TRANSITIONS_WEIGHTS[transition_type]

    bpm_weight = 0.6
    key_weight = 0.4

    return (bpm_score * bpm_weight) + (key_score * key_weight)


def validate_keys(df):
    """Validate that all song keys exist in the relations dictionary"""
    all_valid_keys = set()
    for transitions in ALLOWED_KEY_TRANSITIONS.values():
        all_valid_keys.update(transitions.keys())

    invalid_keys = set(df["key"]) - all_valid_keys
    if invalid_keys:
        print(f"Warning: Found invalid keys in dataset: {invalid_keys}")
        print("These songs will have no valid transitions")

    return len(invalid_keys) == 0


def get_transition_type(song1, song2):
    for transition_type, transitions in ALLOWED_KEY_TRANSITIONS.items():
        if song1["key"] in transitions:
            if song2["key"] in transitions[song1["key"]]:
                return transition_type
    return "incompatible"


def build_compatibility_graph(df):
    """Build a weighted graph of compatible song transitions"""
    graph = defaultdict(list)
    scores = {}  # Store transition scores

    reachable_songs = set()
    for i, song1 in df.iterrows():
        bpm_tolerance = 4
        while True:
            for j, song2 in df.iterrows():
                if i != j:
                    score = calculate_transition_score(song1, song2, bpm_tolerance)
                    if score > 0:  # Only add compatible transitions
                        graph[i].append(j)
                        reachable_songs.add(j)
                        scores[(i, j)] = score
            if len(graph[i]) > 1 or bpm_tolerance > 30:
                break
            bpm_tolerance += 1

    for i, song1 in df.iterrows():
        if len(graph[i]) == 0 and i not in reachable_songs:
            print(f"{i} is unreachable")

    return graph, scores


def _build_reverse_transitions() -> dict[str, dict[str, set[str]]]:
    """Invert ALLOWED_KEY_TRANSITIONS: A→B in forward becomes B→A in reverse."""
    result = {}
    for ttype, forward in ALLOWED_KEY_TRANSITIONS.items():
        rev: dict[str, set[str]] = defaultdict(set)
        for src, targets in forward.items():
            for tgt in targets:
                rev[tgt].add(src)
        result[ttype] = dict(rev)
    return result


REVERSE_KEY_TRANSITIONS = _build_reverse_transitions()


BPM_TOLERANCE = 12


def is_relevant(song, genres: set[str] | None = None, min_rating: int = 80) -> bool:
    if genres is not None and song.genre not in genres:
        return False
    if song.rating < min_rating:
        return False
    comment = (song.comment or "").strip()
    if comment == "ignore" or "mixed" in comment.lower():
        return False
    return True


def filter_candidates(
    candidates,
    played_ids: set[str],
    from_bpm: float,
    to_bpm: float,
    keys: set[str],
    genres: set[str] | None = None,
    min_rating: int = 80,
):
    return [
        s
        for s in candidates
        if s.id not in played_ids
        and is_relevant(s, genres, min_rating)
        and from_bpm <= s.bpm <= to_bpm
        and s.key in keys
    ]


def print_table(title: str, songs) -> None:
    print(f"\n= {title} =")
    if not songs:
        print("  (none)")
        return
    col_id = max(len(s.id) for s in songs)
    col_art = max((len(s.artist) for s in songs), default=6)
    col_name = max((len(s.name) for s in songs), default=4)
    row = f"{{:<{col_id}}}  {{:<{col_art}}}  {{:<{col_name}}}  {{:<7}}  {{:<8}}"
    header = row.format("ID", "Artist", "Name", "BPM", "Key")
    print(header)
    print("-" * len(header))
    for s in songs:
        print(row.format(s.id, s.artist, s.name, f"{s.bpm:.2f}", s.key))


def load_playlist(name: str):
    from music_stuff.lib.lib_apple_music import find_songs_by_playlist_name

    return find_songs_by_playlist_name(name)
