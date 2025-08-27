import pandas as pd
import pulp
from transitions import calculate_transition_score, build_compatibility_graph, validate_keys

def main(source_file, min_songs, max_songs):
    # Load dataset
    songs = pd.read_csv(source_file).set_index('song_id')
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

    # ILP Model
    model = pulp.LpProblem("BestPlaylist", pulp.LpMaximize)

    # Decision variables: x[i,j] = 1 if transition i->j is used
    x = pulp.LpVariable.dicts("x", scores.keys(), lowBound=0, upBound=1, cat=pulp.LpBinary)

    # Objective: maximize total transition score
    lambda_len = 0.01  # tune this weight
    model += pulp.lpSum(scores[i, j] * x[i, j] for (i, j) in scores) \
         + lambda_len * pulp.lpSum(x[i, j] for (i, j) in scores)

    # AFTER defining x[i,j] variables AND before solving:
    # 1. Add start/end node constraints to enforce EXACTLY ONE PATH
    s = pulp.LpVariable.dicts("start", song_ids, cat=pulp.LpBinary)
    t = pulp.LpVariable.dicts("end", song_ids, cat=pulp.LpBinary)

    for i in song_ids:
        out_degree = pulp.lpSum(x[i, j] for j in song_ids if (i, j) in x)
        in_degree = pulp.lpSum(x[j, i] for j in song_ids if (j, i) in x)

        # Start node: out=1, in=0
        model += s[i] <= out_degree
        model += s[i] <= 1 - in_degree
        model += s[i] >= out_degree - in_degree

        # End node: out=0, in=1
        model += t[i] <= 1 - out_degree
        model += t[i] <= in_degree
        model += t[i] >= in_degree - out_degree

    # Enforce exactly ONE start and ONE end node (single path)
    model += pulp.lpSum(s[i] for i in song_ids) == 1
    model += pulp.lpSum(t[i] for i in song_ids) == 1

    # Link path length to edges: total_songs = total_edges + 1
    total_songs = pulp.lpSum(s[i] for i in song_ids) + pulp.lpSum(x[i, j] for (i, j) in x)
    model += total_songs >= min_songs
    model += total_songs <= max_songs

    # Constraints:
    # 1. Each song has at most one outgoing edge
    for i in song_ids:
        model += pulp.lpSum(x[i, j] for j in song_ids if (i, j) in x) <= 1

    # 2. Each song has at most one incoming edge
    for j in song_ids:
        model += pulp.lpSum(x[i, j] for i in song_ids if (i, j) in x) <= 1

    # MTZ variables: u[i] = position of song i in the playlist
    u = pulp.LpVariable.dicts("u", song_ids, lowBound=0, upBound=len(song_ids), cat=pulp.LpInteger)

    # Subtour elimination constraints (Miller–Tucker–Zemlin)
    n = len(song_ids)
    for i in song_ids:
        for j in song_ids:
            if i != j and (i, j) in x:
                model += u[i] - u[j] + n * x[i, j] <= n - 1

    # Solve
    status = model.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=60))

    print(f"Model status: {pulp.LpStatus[status]}")

    # Extract chosen edges
    playlist_edges = {(i, j) for (i, j) in scores if pulp.value(x[i, j]) == 1}

    # Build adjacency map
    next_map = {i: j for (i, j) in playlist_edges}
    prev_map = {j: i for (i, j) in playlist_edges}

    # Find start node (no incoming edge)
    start_nodes = [i for i in song_ids if i not in prev_map]
    if not start_nodes:
        print("No valid playlist found.")
    else:
        current = start_nodes[0]
        playlist = [songs.loc[current]]
        while current in next_map:
            current = next_map[current]
            playlist.append(songs.loc[current])

        print("Best Playlist Order:")
        for idx, song in enumerate(playlist, 1):
            print(f"{idx}. {song.name}")

        print("Total Score:", pulp.value(model.objective))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate optimal music playlist")
    parser.add_argument("source_file", nargs="?", default="songs.csv", help="CSV file with song data")
    parser.add_argument("--min-songs", type=int, default=10, help="Minimum playlist length")
    parser.add_argument("--max-songs", type=int, default=25, help="Maximum playlist length")

    args = parser.parse_args()
    main(args.source_file, args.min_songs, args.max_songs)
