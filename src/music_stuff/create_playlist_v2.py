import pandas as pd
import time
import sys
import os
from music_stuff.lib.lib_transitions import calculate_transition_score, validate_keys, get_transition_type, build_compatibility_graph

def find_best_path_greedy(graph, scores, start_node, df):
    """Find a good path using greedy approach - faster and often better for small datasets"""
    path = [start_node]
    current_node = start_node
    visited = {start_node}
    total_score = 0

    while True:
        # Get all unvisited neighbors with their scores
        candidates = []
        for neighbor in graph[current_node]:
            if neighbor not in visited:
                score = scores[(current_node, neighbor)]
                candidates.append((neighbor, score))

        if not candidates:
            break

        # Choose the best scoring transition
        candidates.sort(key=lambda x: x[1], reverse=True)
        next_node, transition_score = candidates[0]

        path.append(next_node)
        visited.add(next_node)
        total_score += transition_score
        current_node = next_node

    return path, total_score

def find_best_path_dfs(graph, scores, start_node, max_time_seconds=60):
    """Find the best path using DFS with improved scoring"""
    start_time = time.time()
    best_path = []
    best_score = 0

    def dfs(node, path, visited_set, current_score):
        nonlocal best_path, best_score, start_time

        # Check time limit
        if time.time() - start_time > max_time_seconds:
            return

        # Improved path quality: emphasize score over length
        # Small length bonus to break ties
        path_quality = current_score + (len(path) * 2)

        if path_quality > best_score:
            best_path = path.copy()
            best_score = path_quality

        # Sort neighbors by score (best first)
        neighbors_with_scores = [(neighbor, scores.get((node, neighbor), 0))
                                for neighbor in graph[node]]
        neighbors_with_scores.sort(key=lambda x: x[1], reverse=True)

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

def find_longest_playlist(df, max_time_seconds=300, use_greedy=True):
    """Find the best playlist using hybrid approach"""
    print("Validating song keys...")
    validate_keys(df)

    print("Building compatibility graph...")
    graph, scores = build_compatibility_graph(df)

    connection_count = sum(len(neighbors) for neighbors in graph.values())
    print(f"Graph built with {connection_count} connections")

    if connection_count == 0:
        print("No compatible transitions found!")
        return [], None

    best_playlist = []
    best_score = 0
    best_start_song = None

    total_songs = len(df)
    print(f"Trying all {total_songs} starting songs...")

    for i, (idx, song) in enumerate(df.iterrows()):
        # Use greedy first for speed, then DFS for promising starts
        greedy_path, greedy_score = find_best_path_greedy(graph, scores, idx, df)

        path, score = greedy_path, greedy_score

        # If greedy found a decent path and we have time, try DFS
        if use_greedy and len(greedy_path) >= 3 and i < 10:  # Only DFS on top 10 songs
            dfs_path, dfs_score = find_best_path_dfs(graph, scores, idx,
                                                    max_time_seconds // 10)
            if dfs_score > greedy_score:
                path, score = dfs_path, dfs_score

        if score > best_score:
            best_playlist = path
            best_score = score
            best_start_song = idx
            print(f"New best: {len(path)} songs, score: {score:.1f} "
                  f"(avg: {score/max(len(path)-1, 1):.1f} per transition)")
            playlist_df = create_playlist_dataframe(df, best_playlist)
            print(playlist_df.to_string(index=False))

    return best_playlist, best_start_song

def create_playlist_dataframe(df, playlist_indices):
    """Create a DataFrame with the playlist in order, including transition scores"""
    if not playlist_indices:
        return pd.DataFrame()

    playlist_df = df.loc[playlist_indices].copy()
    playlist_df['playlist_position'] = range(1, len(playlist_indices) + 1)

    # Add transition information
    playlist_df['bpm_diff'] = playlist_df['bpm'].diff().shift(-1)

    # Calculate transition scores and types
    transition_scores = []
    transition_types = []

    for i in range(len(playlist_indices) - 1):
        current_song = df.loc[playlist_indices[i]]
        next_song = df.loc[playlist_indices[i + 1]]
        score = calculate_transition_score(current_song, next_song)
        transition_scores.append(score)
        transition_type = get_transition_type(current_song, next_song)
        transition_types.append(transition_type)

    # Add the last row (no transition)
    transition_scores.append(None)
    transition_types.append(None)

    playlist_df['transition_score'] = transition_scores
    playlist_df['transition_type'] = transition_types

    columns = ['playlist_position', 'apple_music_id', 'key', 'bpm',
               'bpm_diff', 'transition_score', 'transition_type']
    return playlist_df[columns]

def add_suffix(filename, suffix, separator='_'):
    if '.' in filename[1:] and not (filename.startswith('.') and filename[1:].find('.') == -1):
        root, ext = os.path.splitext(filename)
        return f"{root}{separator}{suffix}{ext}"
    return f"{filename}{separator}{suffix}"

def main(source_file):
    output_file = add_suffix(source_file, "longest")

    # Load and validate data
    try:
        df = pd.read_csv(source_file)
        print(f"Loaded {len(df)} songs from {source_file}")

        # Check required columns
        required_columns = ['apple_music_id', 'key', 'bpm']
        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        # Sort by BPM for better initial ordering
        df = df.sort_values(by=['bpm']).reset_index(drop=True)

    except Exception as e:
        print(f"Error loading data: {e}")
        return

    print("\nFinding longest playlist...")
    start_time = time.time()

    longest_playlist, best_start = find_longest_playlist(df, max_time_seconds=300)

    end_time = time.time()
    print(f"\nSearch completed in {end_time - start_time:.2f} seconds")

    if longest_playlist:
        print(f"\nLongest playlist found: {len(longest_playlist)} songs")
        playlist_df = create_playlist_dataframe(df, longest_playlist)
        print("\nPlaylist:")
        print(playlist_df.to_string(index=False))

        # Save to CSV
        playlist_df.to_csv(output_file, index=False)
        print(f"\nPlaylist saved to {output_file}")
    else:
        print("No compatible playlist found!")
        print("Check that your song keys are valid (e.g. '6d', '1m') and BPMs allow for transitions.")

if __name__ == "__main__":
    source_file = sys.argv[1] if len(sys.argv) > 1 else "songs.csv"
    main(source_file)
