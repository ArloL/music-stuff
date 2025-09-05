import pandas as pd
import pulp
from collections import defaultdict
from transitions import calculate_transition_score, build_compatibility_graph, validate_keys, get_transition_type

def main(source_file, min_songs, max_songs):
    # Load dataset
    songs = pd.read_csv(source_file).set_index('apple_music_id')
    song_ids = songs.index.tolist()

    print("Validating song keys...")
    validate_keys(songs)

    print("Building compatibility graph...")
    graph, scores = build_compatibility_graph(songs)

    connection_count = sum(len(neighbors) for neighbors in graph.values())
    print(f"Graph built with {connection_count} connections")

    if connection_count == 0:
        print("No compatible transitions found!")
        return

    print(scores)

    # ILP Model
    m = pulp.LpProblem("BestPlaylist", pulp.LpMaximize)

    E = [(i, j) for (i, j) in scores if i != j]
    out_arcs = defaultdict(list)
    in_arcs = defaultdict(list)
    for (i, j) in E:
        out_arcs[i].append((i, j))
        in_arcs[j].append((i, j))

    x = pulp.LpVariable.dicts("x", E, lowBound=0, upBound=1, cat=pulp.LpBinary)
    y = pulp.LpVariable.dicts("y", song_ids, lowBound=0, upBound=1, cat=pulp.LpBinary)
    s = pulp.LpVariable.dicts("s", song_ids, lowBound=0, upBound=1, cat=pulp.LpBinary)
    t = pulp.LpVariable.dicts("t", song_ids, lowBound=0, upBound=1, cat=pulp.LpBinary)

    bigN = len(song_ids)
    u = pulp.LpVariable.dicts("u", song_ids, lowBound=0, upBound=bigN, cat=pulp.LpInteger)

    # Objective
    m += pulp.lpSum(scores[(i, j)] * x[(i, j)] for (i, j) in E)

    # Degree bounds + flow balance
    for i in song_ids:
        m += pulp.lpSum(x[e] for e in out_arcs[i]) <= 1
        m += pulp.lpSum(x[e] for e in in_arcs[i]) <= 1
        m += (pulp.lpSum(x[e] for e in out_arcs[i]) -
            pulp.lpSum(x[e] for e in in_arcs[i]) ==
            s[i] - t[i])

    # Path start/end constraints
    m += pulp.lpSum(s[i] for i in song_ids) == pulp.lpSum(t[i] for i in song_ids)
    m += pulp.lpSum(s[i] for i in song_ids) <= 1
    m += pulp.lpSum(t[i] for i in song_ids) <= 1

    # Node usage consistency
    for i in song_ids:
        m += (pulp.lpSum(x[e] for e in out_arcs[i]) +
            pulp.lpSum(x[e] for e in in_arcs[i]) ==
            2 * y[i] - s[i] - t[i])
        m += u[i] <= bigN * y[i]
        m += u[i] >= y[i]

    # MTZ subtour elimination
    M = bigN
    for (i, j) in E:
        m += u[j] >= u[i] + 1 - M * (1 - x[(i, j)])

    # Solve
    status = m.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=60))

    print(f"Model status: {pulp.LpStatus[status]}")

    print("Selected transitions:")
    for (i,j) in scores:
        if x[i,j].varValue == 1:
            print(f"{i} -> {j}: {scores[(i,j)]}")

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
