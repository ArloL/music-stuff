import pandas as pd
import pulp
from transitions import calculate_transition_score, build_compatibility_graph, validate_keys, get_transition_type

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

    # -------------------
    # Simplified constraints
    # -------------------

    # Degree balances
    outdeg = {i: pulp.lpSum(x[i,j] for j in song_ids if (i,j) in x) for i in song_ids}
    indeg  = {i: pulp.lpSum(x[j,i] for j in song_ids if (j,i) in x) for i in song_ids}

    # Each song has at most one predecessor and one successor
    for i in song_ids:
        model += outdeg[i] <= 1
        model += indeg[i] <= 1

    # Explicit start/end indicators
    is_start = pulp.LpVariable.dicts("is_start", song_ids, 0, 1, cat="Binary")
    is_end   = pulp.LpVariable.dicts("is_end", song_ids, 0, 1, cat="Binary")

    for i in song_ids:
        model += outdeg[i] - indeg[i] == is_start[i] - is_end[i]

    model += pulp.lpSum(is_start[i] for i in song_ids) == 1
    model += pulp.lpSum(is_end[i] for i in song_ids) == 1

    # Flow variables for subtour elimination
    f = pulp.LpVariable.dicts("f", scores.keys(), lowBound=0, upBound=len(song_ids)-1, cat="Integer")

    # Flow conservation: each visited node (except start) consumes 1 unit of flow
    for i in song_ids:
        inflow  = pulp.lpSum(f[j,i] for j in song_ids if (j,i) in f)
        outflow = pulp.lpSum(f[i,j] for j in song_ids if (i,j) in f)

        # Start node: injects (total_songs - 1) units
        model += inflow - outflow == indeg[i] - is_start[i] * (max_songs - 1)

    # Capacity: flow only if edge is used
    for (i,j) in f:
        model += f[i,j] <= (len(song_ids)-1) * x[i,j]

    # Playlist length bounds
    total_songs = pulp.lpSum(x[i,j] for (i,j) in x) + 1
    model += total_songs >= min_songs
    model += total_songs <= max_songs

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
    for current in start_nodes:
        playlist = [songs.loc[current]]
        while current in next_map:
            current = next_map[current]
            playlist.append(songs.loc[current])

        print("Playlist Order:")
        for i in range(len(playlist)):
            song = playlist[i]
            if i + 2 > len(playlist):
                print(f"{i + 1}. {song.name}")
            else:
                next_song = playlist[i + 1]
                score = calculate_transition_score(song, next_song)
                transition_type = get_transition_type(song, next_song)
                print(f"{i + 1}. {song.name} {song['bpm']} {score} {transition_type}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate optimal music playlist")
    parser.add_argument("source_file", nargs="?", default="songs.csv", help="CSV file with song data")
    parser.add_argument("--min-songs", type=int, default=10, help="Minimum playlist length")
    parser.add_argument("--max-songs", type=int, default=25, help="Maximum playlist length")

    args = parser.parse_args()
    main(args.source_file, args.min_songs, args.max_songs)
