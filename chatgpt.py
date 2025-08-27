import pandas as pd
import pulp
from transitions import calculate_transition_score
import sys

def main(source_file):
    # Load dataset
    songs = pd.read_csv(source_file).set_index('song_id')
    song_ids = songs.index.tolist()

    # Build score matrix
    scores = {
        (i, j): calculate_transition_score(songs.loc[i], songs.loc[j])
        for i in song_ids for j in song_ids if i != j
    }

    # ILP Model
    model = pulp.LpProblem("BestPlaylist", pulp.LpMaximize)

    # Decision variables: x[i,j] = 1 if transition i->j is used
    x = pulp.LpVariable.dicts("x", scores.keys(), lowBound=0, upBound=1, cat=pulp.LpBinary)

    # Objective: maximize total transition score
    model += pulp.lpSum(scores[i, j] * x[i, j] for (i, j) in scores)

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
    model.solve(pulp.PULP_CBC_CMD(msg=False))

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
        playlist = [current]
        while current in next_map:
            current = next_map[current]
            playlist.append(current)

        print("Best Playlist Order:")
        for idx, song in enumerate(playlist, 1):
            print(f"{idx}. {song}")

        print("Total Score:", pulp.value(model.objective))

if __name__ == "__main__":
    source_file = sys.argv[1] if len(sys.argv) > 1 else "songs.csv"
    main(source_file)
