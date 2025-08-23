import pandas as pd
from collections import defaultdict
import time

def calculate_transition_score(song1, song2, key_relations, bpm_tolerance):
    """Calculate a weighted score for the transition between two songs"""
    # Check BPM difference (within 4 BPM)
    bpm_diff = song2['bpm'] - song1['bpm']  # Positive = going up, Negative = going down
    abs_bpm_diff = abs(bpm_diff)

    if abs_bpm_diff > bpm_tolerance:
        return 0  # Incompatible transition

    # BPM scoring (higher is better)
    if abs_bpm_diff == 0:
        bpm_score = 100  # Perfect BPM match
    elif bpm_diff > 0:  # Going up in BPM
        bpm_score = 100 - abs_bpm_diff       # Slight penalty for going up
    else:  # Going down in BPM
        bpm_score = 80 - (abs_bpm_diff * 5)  # Larger penalty for going down

    # Key transition scoring
    song1_key = song1['key']
    song2_key = song2['key']
    key_score = 0

    # Define weights for different transition types (higher is better)
    transition_weights = {
        "matching": 100,           # Best - harmonic matching
        "boost": 90,               # Good - one step up
        "boost boost": 80,         # Okay - two steps up
        "boost boost boost": 70,   # Acceptable - three steps up
        "drop": 60,                # Not bad - one step down
        "drop drop": 50,           # Sure - why not
        "drop drop drop": 40       # No other way out but to do this
    }

    # Find the best matching transition type
    for transition_type, transitions in key_relations.items():
        if song1_key in transitions:
            if song2_key in transitions[song1_key]:
                key_score = max(key_score, transition_weights[transition_type])

    if key_score == 0:
        return 0  # No valid key transition found

    # Combined score (weighted average)
    # You can adjust these weights based on what's more important to you
    bpm_weight = 0.6
    key_weight = 0.4

    total_score = (bpm_score * bpm_weight) + (key_score * key_weight)
    return total_score

def build_compatibility_graph(df, key_relations):
    """Build a weighted graph of compatible song transitions"""
    graph = defaultdict(list)
    scores = {}  # Store transition scores

    for i, song1 in df.iterrows():
        bpm_tolerance = 4
        while True:
            for j, song2 in df.iterrows():
                if i != j:
                    score = calculate_transition_score(song1, song2, key_relations, bpm_tolerance)
                    if score > 0:  # Only add compatible transitions
                        graph[i].append(j)
                        scores[(i, j)] = score
            if len(graph[i]) > 2 or bpm_tolerance > 20:
                break
            bpm_tolerance += 1

    return graph, scores

def find_best_weighted_path_dfs(graph, scores, start_node, max_time_seconds=300):
    """Find the path with the best weighted score using DFS"""
    start_time = time.time()
    best_path = []
    best_score = 0

    def dfs(node, path, visited_set, current_score):
        nonlocal best_path, best_score, start_time

        # Check time limit
        if time.time() - start_time > max_time_seconds:
            return

        # Update best path if current is better
        # We'll use a combination of path length and total score
        path_quality = current_score + (len(path) * 20)  # Bonus for longer paths

        if path_quality > best_score:
            best_path = path.copy()
            best_score = path_quality

        # Sort neighbors by score for better paths first
        neighbors_with_scores = [(neighbor, scores.get((node, neighbor), 0)) for neighbor in graph[node]]
        neighbors_with_scores.sort(key=lambda x: x[1], reverse=True)  # Best scores first

        # Explore neighbors
        for neighbor, transition_score in neighbors_with_scores:
            if neighbor not in visited_set:
                visited_set.add(neighbor)
                path.append(neighbor)
                dfs(neighbor, path, visited_set, current_score + transition_score)
                path.pop()
                visited_set.remove(neighbor)

    visited_set = {start_node}
    dfs(start_node, [start_node], visited_set, 0)
    return best_path, best_score

def find_longest_playlist(df, key_relations, max_time_seconds=300):
    """Find the best weighted playlist"""
    print("Building compatibility graph...")
    graph, scores = build_compatibility_graph(df, key_relations)

    print(f"Graph built with {sum(len(neighbors) for neighbors in graph.values())} connections")

    best_playlist = []
    best_score = 0
    best_start_song = None

    # Try starting from each song (or a subset for very large datasets)
    total_songs = len(df)
    songs_to_try = min(total_songs, 50)  # Limit starting points for large datasets

    print(f"Trying {songs_to_try} different starting songs...")

    for i, (idx, song) in enumerate(df.head(songs_to_try).iterrows()):
        if i % 10 == 0:
            print(f"Progress: {i+1}/{songs_to_try}")

        # Find best weighted path starting from this song
        path, score = find_best_weighted_path_dfs(graph, scores, idx, max_time_seconds//songs_to_try)

        if score > best_score:
            best_playlist = path
            best_score = score
            best_start_song = idx
            print(f"New best playlist found: {len(path)} songs, score: {score:.1f} (starting with: {song['song_id']})")

    return best_playlist, best_start_song

def create_playlist_dataframe(df, playlist_indices, key_relations):
    """Create a DataFrame with the playlist in order, including transition scores"""
    if not playlist_indices:
        return pd.DataFrame()

    playlist_df = df.loc[playlist_indices].copy()
    playlist_df['playlist_position'] = range(1, len(playlist_indices) + 1)

    # Add transition information
    playlist_df['next_song'] = playlist_df['song_id'].shift(-1)
    playlist_df['bpm_diff_to_next'] = playlist_df['bpm'].diff().shift(-1)

    # Calculate transition scores
    transition_scores = []
    transition_types = []

    for i in range(len(playlist_indices) - 1):
        current_song = df.loc[playlist_indices[i]]
        next_song = df.loc[playlist_indices[i + 1]]
        score = calculate_transition_score(current_song, next_song, key_relations, 20)
        transition_scores.append(score)

        # Find the transition type used
        transition_type = "unknown"
        for t_type, transitions in key_relations.items():
            if current_song['key'] in transitions:
                if next_song['key'] in transitions[current_song['key']]:
                    transition_type = t_type
                    break
        transition_types.append(transition_type)

    # Add the last row (no transition)
    transition_scores.append(None)
    transition_types.append(None)

    playlist_df['transition_score'] = transition_scores
    playlist_df['transition_type'] = transition_types

    columns = ['playlist_position', 'song_id', 'key', 'bpm', 'next_song',
               'bpm_diff_to_next', 'transition_score', 'transition_type']
    return playlist_df[columns]

def main():
    # Key mapping
    key_type_relations = {
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

    df = pd.read_csv('songs.csv')
    print(f"Loaded {len(df)} songs")

    # Find the longest playlist
    print("\nFinding longest playlist...")
    start_time = time.time()

    longest_playlist, best_start = find_longest_playlist(df, key_type_relations, max_time_seconds=300)

    end_time = time.time()
    print(f"\nSearch completed in {end_time - start_time:.2f} seconds")

    if longest_playlist:
        print(f"\nLongest playlist found: {len(longest_playlist)} songs")
        playlist_df = create_playlist_dataframe(df, longest_playlist, key_type_relations)
        print("\nPlaylist:")
        print(playlist_df.to_string(index=False))

        # Save to CSV
        output_file = 'longest_playlist.csv'
        playlist_df.to_csv(output_file, index=False)
        print(f"\nPlaylist saved to {output_file}")

        # Print some statistics
        print(f"\nPlaylist Statistics:")
        print(f"Total songs: {len(longest_playlist)}")
        print(f"BPM range: {playlist_df['bpm'].min():.1f} - {playlist_df['bpm'].max():.1f}")
        print(f"Average BPM: {playlist_df['bpm'].mean():.1f}")
        if len(playlist_df) > 1:
            max_bpm_diff = playlist_df['bpm_diff_to_next'].abs().max()
            print(f"Max BPM transition: {max_bpm_diff:.1f}")
    else:
        print("No compatible playlist found!")

if __name__ == "__main__":
    main()
