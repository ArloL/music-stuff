import pandas as pd
from collections import defaultdict
import time

def is_compatible(song1, song2, key_relations, bpm_tolerance):
    """Check if two songs are compatible based on key transitions and BPM difference"""
    # Check BPM difference (within 4 BPM)
    bpm_diff = abs(song1['bpm'] - song2['bpm'])
    if bpm_diff > bpm_tolerance:
        return False

    # Check key compatibility
    song1_key = song1['key']
    song2_key = song2['key']

    # Check all transition types
    for transition_type, transitions in key_relations.items():
        if song1_key in transitions:
            if song2_key in transitions[song1_key]:
                return True

    return False

def build_compatibility_graph(df, key_relations):
    """Build a graph of compatible song transitions"""
    graph = defaultdict(list)

    for i, song1 in df.iterrows():
        bpm_tolerance = 4
        while True:
            for j, song2 in df.iterrows():
                if i != j and is_compatible(song1, song2, key_relations, bpm_tolerance):
                    graph[i].append(j)
            if len(graph[i]) > 2 or bpm_tolerance > 20:
                break
            bpm_tolerance += 1

    return graph

def find_longest_path_dfs(graph, start_node, visited, current_path, max_time_seconds=120):
    """Find longest path using DFS with time limit"""
    start_time = time.time()
    best_path = []

    def dfs(node, path, visited_set):
        nonlocal best_path, start_time

        # Check time limit
        if time.time() - start_time > max_time_seconds:
            return

        if len(path) > len(best_path):
            best_path = path.copy()

        # Explore neighbors
        for neighbor in graph[node]:
            if neighbor not in visited_set:
                visited_set.add(neighbor)
                path.append(neighbor)
                dfs(neighbor, path, visited_set)
                path.pop()
                visited_set.remove(neighbor)

    visited_set = {start_node}
    dfs(start_node, [start_node], visited_set)
    return best_path

def find_longest_playlist(df, key_relations, max_time_seconds=120):
    """Find the longest possible playlist"""
    print("Building compatibility graph...")
    graph = build_compatibility_graph(df, key_relations)

    print(f"Graph built with {sum(len(neighbors) for neighbors in graph.values())} connections")

    longest_playlist = []
    best_start_song = None

    # Try starting from each song (or a subset for very large datasets)
    total_songs = len(df)
    songs_to_try = min(total_songs, 50)  # Limit starting points for large datasets

    print(f"Trying {songs_to_try} different starting songs...")

    for i, (idx, song) in enumerate(df.head(songs_to_try).iterrows()):
        if i % 10 == 0:
            print(f"Progress: {i+1}/{songs_to_try}")

        # Find longest path starting from this song
        path = find_longest_path_dfs(graph, idx, set(), [], max_time_seconds//songs_to_try)

        if len(path) > len(longest_playlist):
            longest_playlist = path
            best_start_song = idx
            print(f"New best playlist found: {len(path)} songs (starting with: {song['song_id']})")

    return longest_playlist, best_start_song

def create_playlist_dataframe(df, playlist_indices):
    """Create a DataFrame with the playlist in order"""
    if not playlist_indices:
        return pd.DataFrame()

    playlist_df = df.loc[playlist_indices].copy()
    playlist_df['playlist_position'] = range(1, len(playlist_indices) + 1)

    # Add transition information
    playlist_df['next_song'] = playlist_df['song_id'].shift(-1)
    playlist_df['bpm_diff_to_next'] = playlist_df['bpm'].diff().shift(-1)

    return playlist_df[['playlist_position', 'song_id', 'key', 'bpm', 'next_song', 'bpm_diff_to_next']]

def main():
    # Key mapping
    key_type_relations = {
        "matching": {
            11: [11, 14], 13: [13, 16], 15: [15, 18], 17: [17, 20], 19: [19, 22], 21: [21, 24],
            23: [23, 2], 1: [1, 4], 3: [3, 6], 5: [5, 8], 7: [7, 10], 9: [9, 12],
            12: [12, 9], 14: [14, 11], 16: [16, 13], 18: [18, 15], 20: [20, 17], 22: [22, 19],
            24: [24, 21], 2: [2, 23], 4: [4, 1], 6: [6, 3], 8: [8, 5], 10: [10, 7]
        },
        "boost": {
            11: [13], 13: [15], 15: [17], 17: [19], 19: [21], 21: [23], 23: [1], 1: [3], 3: [5],
            5: [7], 7: [9], 9: [11], 12: [11, 14], 14: [13, 16], 16: [15, 18], 18: [17, 20],
            20: [19, 22], 22: [21, 24], 24: [23, 2], 2: [1, 4], 4: [3, 6], 6: [5, 8], 8: [7, 10], 10: [9, 12]
        },
        "boost boost": {
            11: [5], 13: [7], 15: [9], 17: [11], 19: [13], 21: [15], 23: [17], 1: [19], 3: [21],
            5: [23], 7: [1], 9: [3], 12: [6], 14: [8], 16: [10], 18: [12], 20: [14], 22: [16],
            24: [18], 2: [20], 4: [22], 6: [24], 8: [2], 10: [4]
        },
        "boost boost boost": {
            11: [15, 1], 13: [17, 3], 15: [19, 5], 17: [21, 7], 19: [23, 9], 21: [1, 11],
            23: [3, 13], 1: [5, 15], 3: [7, 17], 5: [9, 19], 7: [11, 21], 9: [13, 23],
            12: [16, 2], 14: [18, 4], 16: [20, 6], 18: [22, 8], 20: [24, 10], 22: [2, 12],
            24: [4, 14], 2: [6, 16], 4: [8, 18], 6: [10, 20], 8: [12, 22], 10: [14, 24]
        }
    }

    df = pd.read_csv('songs.csv')
    print(f"Loaded {len(df)} songs")

    # Find the longest playlist
    print("\nFinding longest playlist...")
    start_time = time.time()

    longest_playlist, best_start = find_longest_playlist(df, key_type_relations, max_time_seconds=120)

    end_time = time.time()
    print(f"\nSearch completed in {end_time - start_time:.2f} seconds")

    if longest_playlist:
        print(f"\nLongest playlist found: {len(longest_playlist)} songs")
        playlist_df = create_playlist_dataframe(df, longest_playlist)
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
