import pandas as pd
import pulp
from collections import defaultdict
from transitions import calculate_transition_score, build_compatibility_graph, validate_keys, get_transition_type

def main(source_file, min_songs, max_songs):
    # Load dataset
    songs = pd.read_csv(source_file).set_index('apple_music_id')
    song_ids = songs.index.tolist()
    n_songs = len(song_ids)

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

    # Binary variables: s[i] = 1 if song i is selected in the playlist
    s = pulp.LpVariable.dicts("s", song_ids, cat=pulp.LpBinary)

    # Position variables for MTZ subtour elimination: u[i] = position of song i in path
    u = pulp.LpVariable.dicts("u", song_ids, lowBound=0, upBound=n_songs-1, cat=pulp.LpInteger)

    # Objective: maximize sum of transition scores
    prob += pulp.lpSum(scores[i,j] * x[i,j] for (i,j) in scores.keys())

    # Link selection and transition variables
    for node in song_ids:
        out_edges = [(i,j) for (i,j) in scores.keys() if i == node]
        in_edges = [(i,j) for (i,j) in scores.keys() if j == node]

        # Song is selected if it has any outgoing or incoming transition
        if out_edges or in_edges:
            prob += s[node] <= pulp.lpSum(x[i,j] for (i,j) in out_edges) + pulp.lpSum(x[i,j] for (i,j) in in_edges)
            prob += pulp.lpSum(x[i,j] for (i,j) in out_edges) + pulp.lpSum(x[i,j] for (i,j) in in_edges) <= s[node] * 2

    # Flow conservation constraints for simple path
    for node in song_ids:
        out_edges = [(i,j) for (i,j) in scores.keys() if i == node]
        in_edges = [(i,j) for (i,j) in scores.keys() if j == node]

        # Each selected song has at most 1 outgoing and 1 incoming edge
        if out_edges:
            prob += pulp.lpSum(x[i,j] for (i,j) in out_edges) <= 1
        if in_edges:
            prob += pulp.lpSum(x[i,j] for (i,j) in in_edges) <= 1

    # Exactly one start node (no incoming edges) and one end node (no outgoing edges)
    start_indicators = []
    end_indicators = []

    for node in song_ids:
        out_edges = [(i,j) for (i,j) in scores.keys() if i == node]
        in_edges = [(i,j) for (i,j) in scores.keys() if j == node]

        if out_edges and in_edges:
            # Internal node: if selected, must have exactly 1 in and 1 out (or be start/end)
            is_start = pulp.LpVariable(f"start_{node}", cat=pulp.LpBinary)
            is_end = pulp.LpVariable(f"end_{node}", cat=pulp.LpBinary)

            # If selected and not start, must have incoming edge
            prob += pulp.lpSum(x[i,j] for (i,j) in in_edges) >= s[node] - is_start
            # If selected and not end, must have outgoing edge
            prob += pulp.lpSum(x[i,j] for (i,j) in out_edges) >= s[node] - is_end

            start_indicators.append(is_start)
            end_indicators.append(is_end)

        elif out_edges and not in_edges:
            # Can only be start node
            is_start = pulp.LpVariable(f"start_{node}", cat=pulp.LpBinary)
            prob += s[node] == is_start
            start_indicators.append(is_start)

        elif in_edges and not out_edges:
            # Can only be end node
            is_end = pulp.LpVariable(f"end_{node}", cat=pulp.LpBinary)
            prob += s[node] == is_end
            end_indicators.append(is_end)

    # Exactly one start and one end
    if start_indicators:
        prob += pulp.lpSum(start_indicators) == 1
    if end_indicators:
        prob += pulp.lpSum(end_indicators) == 1

    # MTZ subtour elimination constraints
    for (i, j) in scores.keys():
        prob += u[j] >= u[i] + 1 - n_songs * (1 - x[i,j])

    # Length constraints
    total_transitions = pulp.lpSum(x[i,j] for (i,j) in scores.keys())
    prob += total_transitions >= min_songs - 1  # n songs = n-1 transitions
    prob += total_transitions <= max_songs - 1

    # Solve
    print(f"Solving with constraints: {min_songs}-{max_songs} songs...")
    status = prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=120))

    print(f"Model status: {pulp.LpStatus[status]}")

    if status != pulp.LpStatusOptimal:
        print("No optimal solution found. Try relaxing constraints.")
        return

    # Extract chosen edges
    playlist_edges = {(i, j) for (i, j) in scores if pulp.value(x[(i, j)]) == 1}

    if not playlist_edges:
        print("No transitions selected.")
        return

    # Build adjacency map
    next_map = {i: j for (i, j) in playlist_edges}
    prev_map = {j: i for (i, j) in playlist_edges}

    # Find start node (no incoming edge)
    start_nodes = [i for i in song_ids if i in next_map and i not in prev_map]

    if not start_nodes:
        print("No valid start node found.")
        return

    # Build playlist
    current = start_nodes[0]
    playlist = [songs.loc[current]]
    total_score = 0

    while current in next_map:
        next_song = next_map[current]
        playlist.append(songs.loc[next_song])
        total_score += scores[(current, next_song)]
        current = next_song

    print(f"\nOptimal Playlist ({len(playlist)} songs, score: {total_score:.2f}):")
    for i in range(len(playlist)):
        song = playlist[i]
        if i + 1 < len(playlist):
            next_song = playlist[i + 1]
            score = calculate_transition_score(song, next_song)
            transition_type = get_transition_type(song, next_song)
            print(f"{i + 1}. {song['artist']} - {song['name']} (BPM: {song['bpm']}) → {score:.2f} ({transition_type})")
        else:
            print(f"{i + 1}. {song['artist']} - {song['name']} (BPM: {song['bpm']})")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate optimal music playlist")
    parser.add_argument("source_file", nargs="?", default="songs.csv", help="CSV file with song data")
    parser.add_argument("--min-songs", type=int, default=10, help="Minimum playlist length")
    parser.add_argument("--max-songs", type=int, default=25, help="Maximum playlist length")

    args = parser.parse_args()
    main(args.source_file, args.min_songs, args.max_songs)
