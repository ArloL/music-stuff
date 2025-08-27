from collections import defaultdict

ALLOWED_KEY_TRANSITIONS = {
    "drop drop drop": {
        11: [7],
        13: [9],
        15: [11],
        17: [13],
        19: [15],
        21: [17],
        23: [19],
        1: [21],
        3: [23],
        5: [1],
        7: [3],
        9: [5],
        12: [8],
        14: [10],
        16: [12],
        18: [14],
        20: [16],
        22: [18],
        24: [20],
        2: [22],
        4: [24],
        6: [2],
        8: [4],
        10: [6]
    },
    "drop drop": {
        11: [17],
        13: [19],
        15: [21],
        17: [23],
        19: [1],
        21: [3],
        23: [5],
        1: [7],
        3: [9],
        5: [11],
        7: [13],
        9: [15],
        12: [18],
        14: [20],
        16: [22],
        18: [24],
        20: [2],
        22: [4],
        24: [6],
        2: [8],
        4: [10],
        6: [12],
        8: [14],
        10: [16]
    },
    "drop" :{
        11: [12, 9],
        13: [14, 11],
        15: [16, 13],
        17: [18, 15],
        19: [20, 17],
        21: [22, 19],
        23: [24, 21],
        1: [2, 23],
        3: [4, 1],
        5: [6, 3],
        7: [8, 5],
        9: [10, 7],
        12: [10],
        14: [12],
        16: [14],
        18: [16],
        20: [18],
        22: [20],
        24: [22],
        2: [24],
        4: [2],
        6: [4],
        8: [6],
        10: [8]
    },
    "matching": {
        11: [11, 14],
        13: [13, 16],
        15: [15, 18],
        17: [17, 20],
        19: [19, 22],
        21: [21, 24],
        23: [23, 2],
        1: [1, 4],
        3: [3, 6],
        5: [5, 8],
        7: [7, 10],
        9: [9, 12],
        12: [12, 9],
        14: [14, 11],
        16: [16, 13],
        18: [18, 15],
        20: [20, 17],
        22: [22, 19],
        24: [24, 21],
        2: [2, 23],
        4: [4, 1],
        6: [6, 3],
        8: [8, 5],
        10: [10, 7]
    },
    "boost": {
        11: [13],
        13: [15],
        15: [17],
        17: [19],
        19: [21],
        21: [23],
        23: [1],
        1: [3],
        3: [5],
        5: [7],
        7: [9],
        9: [11],
        12: [11, 14],
        14: [13, 16],
        16: [15, 18],
        18: [17, 20],
        20: [19, 22],
        22: [21, 24],
        24: [23, 2],
        2: [1, 4],
        4: [3, 6],
        6: [5, 8],
        8: [7, 10],
        10: [9, 12]
    },
    "boost boost": {
        11: [5],
        13: [7],
        15: [9],
        17: [11],
        19: [13],
        21: [15],
        23: [17],
        1: [19],
        3: [21],
        5: [23],
        7: [1],
        9: [3],
        12: [6],
        14: [8],
        16: [10],
        18: [12],
        20: [14],
        22: [16],
        24: [18],
        2: [20],
        4: [22],
        6: [24],
        8: [2],
        10: [4]
    },
    "boost boost boost": {
        11: [15, 1],
        13: [17, 3],
        15: [19, 5],
        17: [21, 7],
        19: [23, 9],
        21: [1, 11],
        23: [3, 13],
        1: [5, 15],
        3: [7, 17],
        5: [9, 19],
        7: [11, 21],
        9: [13, 23],
        12: [16, 2],
        14: [18, 4],
        16: [20, 6],
        18: [22, 8],
        20: [24, 10],
        22: [2, 12],
        24: [4, 14],
        2: [6, 16],
        4: [8, 18],
        6: [10, 20],
        8: [12, 22],
        10: [14, 24]
    }
}

TRANSITIONS_WEIGHTS ={
    "matching": 100,           # Perfect harmonic match
    "boost": 95,               # Good energy increase
    "boost boost": 85,         # Moderate energy jump
    "boost boost boost": 50,   # Large energy jump
    "drop": 80,                # Good for breakdowns
    "drop drop": 40,           # Moderate energy drop
    "drop drop drop": 30       # Large energy drop
}

def calculate_transition_score(song1, song2, bpm_tolerance=20):
    """Calculate a weighted score for the transition between two songs"""

    bpm_diff = song2['bpm'] - song1['bpm']
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
    if transition_type == 'incompatible':
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

    invalid_keys = set(df['key']) - all_valid_keys
    if invalid_keys:
        print(f"Warning: Found invalid keys in dataset: {invalid_keys}")
        print("These songs will have no valid transitions")

    return len(invalid_keys) == 0

def get_transition_type(song1, song2):
    for transition_type, transitions in ALLOWED_KEY_TRANSITIONS.items():
        if song1['key'] in transitions:
            if song2['key'] in transitions[song1['key']]:
                return transition_type
    return 'incompatible'

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
        if len(graph[i]) == 0 and not i in reachable_songs:
            print(f"{i} is unreachable")

    return graph, scores
