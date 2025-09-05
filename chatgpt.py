import pandas as pd
import pulp
from collections import defaultdict
from transitions import calculate_transition_score, build_compatibility_graph, validate_keys, get_transition_type

def main(source_file, min_songs, max_songs):
    # Load dataset
    songs = pd.read_csv(source_file).set_index('apple_music_id')
    song_ids = songs.index.tolist()
    n_songs=len(song_ids)

    print("Validating song keys...")
    validate_keys(songs)

    print("Building compatibility graph...")
    graph, scores = build_compatibility_graph(songs)

    connection_count = sum(len(neighbors) for neighbors in graph.values())
    print(f"Graph built with {connection_count} connections")

    if connection_count == 0:
        print("No compatible transitions found!")
        return

    # ILP Model
    prob = pulp.LpProblem("BestPlaylist", pulp.LpMaximize)

    # Decision variables: x[i,j] = 1 if song i transitions to song j
    x = pulp.LpVariable.dicts("x", scores.keys(), cat=pulp.LpBinary)

    # Position variables for MTZ subtour elimination: u[i] = position of song i in path
    u = pulp.LpVariable.dicts("u", song_ids, lowBound=0, upBound=n_songs-1, cat=pulp.LpInteger)

    # Objective: maximize sum of transition scores
    prob += pulp.lpSum(scores[i,j] * x[i,j] for (i,j) in scores.keys())

    # Flow conservation constraints
    for node in song_ids:
        # Out-degree <= 1 (each song can transition to at most one other)
        out_edges = [(i,j) for (i,j) in scores.keys() if i == node]
        if out_edges:
            prob += pulp.lpSum(x[i,j] for (i,j) in out_edges) <= 1

        # In-degree <= 1 (each song can be transitioned to by at most one other)
        in_edges = [(i,j) for (i,j) in scores.keys() if j == node]
        if in_edges:
            prob += pulp.lpSum(x[i,j] for (i,j) in in_edges) <= 1

    # MTZ subtour elimination constraints
    # If x[i,j] = 1, then u[j] >= u[i] + 1 (ensures proper ordering)
    for (i, j) in scores.keys():
        prob += u[j] >= u[i] + 1 - n_songs * (1 - x[i,j])

    # Solve
    status = prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=60))

    print(f"Model status: {pulp.LpStatus[status]}")

    # Extract chosen edges
    playlist_edges = {(i, j) for (i, j) in scores if pulp.value(x[(i, j)]) == 1}

    # Build adjacency map
    next_map = {i: j for (i, j) in playlist_edges}
    prev_map = {j: i for (i, j) in playlist_edges}

    # Find start node (no incoming edge)
    start_nodes = [i for i in song_ids if i not in prev_map]
    if not start_nodes:
        print("No valid playlist found.")
    for current in start_nodes:
        playlist = [songs.loc[current]]
        while current in next_map:
            current = next_map[current]
            playlist.append(songs.loc[current])

        print("Playlist Order:")
        for i in range(len(playlist)):
            song = playlist[i]
            if i + 2 > len(playlist):
                print(f"{i + 1}. {song['artist']} - {song['name']}")
            else:
                next_song = playlist[i + 1]
                score = calculate_transition_score(song, next_song)
                transition_type = get_transition_type(song, next_song)
                print(f"{i + 1}. {song['artist']} - {song['name']} {song['bpm']} {score} {transition_type}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate optimal music playlist")
    parser.add_argument("source_file", nargs="?", default="songs.csv", help="CSV file with song data")
    parser.add_argument("--min-songs", type=int, default=10, help="Minimum playlist length")
    parser.add_argument("--max-songs", type=int, default=25, help="Maximum playlist length")

    args = parser.parse_args()
    main(args.source_file, args.min_songs, args.max_songs)
