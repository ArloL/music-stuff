import heapq
import itertools
import time
import os
import sys
import argparse
import pandas as pd
from music_stuff.lib.lib_transitions import (
    calculate_transition_score, validate_keys,
    get_transition_type, build_compatibility_graph,
)


def astar_search(graph, scores, min_length, max_length, time_limit, start_nodes):
    """A* search for best playlist. Returns (best_path, best_score)."""
    start_time = time.time()
    max_score = max(scores.values()) if scores else 0.0

    best_path = []
    best_complete_score = 0.0

    counter = itertools.count()
    # (-f, tie_counter, g, path_list, visited_frozenset)
    heap = []

    initial_h = max_score * min_length
    for node in start_nodes:
        f = initial_h
        heapq.heappush(heap, (-f, next(counter), 0.0, [node], frozenset([node])))

    while heap:
        if time.time() - start_time > time_limit:
            break

        neg_f, _, g, path, visited = heapq.heappop(heap)
        f = -neg_f

        # Prune: can't beat current best
        if f <= best_complete_score:
            continue

        current = path[-1]

        # Record if long enough
        if len(path) >= min_length and g > best_complete_score:
            best_complete_score = g
            best_path = path

        # Don't expand beyond max_length
        if max_length is not None and len(path) >= max_length:
            continue

        for neighbor in graph[current]:
            if neighbor in visited:
                continue
            edge_score = scores[(current, neighbor)]
            new_g = g + edge_score
            remaining = max(0, min_length - len(path) - 1)
            new_h = max_score * remaining
            new_f = new_g + new_h
            if new_f <= best_complete_score:
                continue
            new_visited = visited | {neighbor}
            heapq.heappush(heap, (-new_f, next(counter), new_g, path + [neighbor], new_visited))

    return best_path, best_complete_score


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

    columns = ['playlist_position', 'apple_music_id', 'artist', 'name', 'key', 'bpm',
               'bpm_diff', 'transition_score', 'transition_type']
    return playlist_df[columns]


def add_suffix(filename, suffix, separator='_'):
    if '.' in filename[1:] and not (filename.startswith('.') and filename[1:].find('.') == -1):
        root, ext = os.path.splitext(filename)
        return f"{root}{separator}{suffix}{ext}"
    return f"{filename}{separator}{suffix}"


def main(source_file, min_length, max_length, time_limit, start_song):
    output_file = add_suffix(source_file, "playlist_v3")

    try:
        df = pd.read_csv(source_file)
        print(f"Loaded {len(df)} songs from {source_file}")

        required_columns = ['apple_music_id', 'key', 'bpm']
        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        df = df.sort_values(by=['bpm']).reset_index(drop=True)

    except Exception as e:
        print(f"Error loading data: {e}")
        return

    validate_keys(df)
    print("Building compatibility graph...")
    graph, scores = build_compatibility_graph(df)

    connection_count = sum(len(neighbors) for neighbors in graph.values())
    print(f"Graph built with {connection_count} connections")

    if connection_count == 0:
        print("No compatible transitions found!")
        return

    # Determine start nodes
    if start_song is not None:
        matches = df.index[df['apple_music_id'] == start_song].tolist()
        if not matches:
            print(f"Error: song_id '{start_song}' not found in {source_file}")
            return
        start_nodes = matches
    else:
        start_nodes = list(df.index)

    print(f"Running A* search (min_length={min_length}, max_length={max_length}, "
          f"time_limit={time_limit}s, {len(start_nodes)} start node(s))...")

    search_start = time.time()
    best_path, best_score = astar_search(
        graph, scores, min_length, max_length, time_limit, start_nodes
    )
    elapsed = time.time() - search_start
    print(f"Search completed in {elapsed:.2f} seconds")

    if best_path:
        print(f"\nPlaylist found: {len(best_path)} songs, score: {best_score:.1f} "
              f"(avg: {best_score / max(len(best_path) - 1, 1):.1f} per transition)")
        playlist_df = create_playlist_dataframe(df, best_path)
        print("\nPlaylist:")
        print(playlist_df.to_string(index=False))
        playlist_df.to_csv(output_file, index=False)
        print(f"\nPlaylist saved to {output_file}")
    else:
        print("No playlist found meeting the minimum length requirement.")
        print(f"Try reducing --min-length (currently {min_length}) or increasing --time-limit.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a playlist using A* search")
    parser.add_argument("source_file", nargs="?", default="songs.csv")
    parser.add_argument("--min-length", type=int, default=10)
    parser.add_argument("--max-length", type=int, default=None)
    parser.add_argument("--time-limit", type=float, default=60.0)
    parser.add_argument("--start-song", type=str, default=None)
    args = parser.parse_args()

    main(args.source_file, args.min_length, args.max_length, args.time_limit, args.start_song)
