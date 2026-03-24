import math

import networkx as nx
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, callback, dcc, html

key_type_relations = {
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
        10: [10, 7],
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
        10: [9, 12],
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
        10: [4],
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
        10: [14, 24],
    },
}


def build_network(df, selected_relations, max_connections=3):
    """Build network graph with BPM tolerance per song and connection limiting"""
    G = nx.DiGraph()

    # Add all songs as nodes
    for _, row in df.iterrows():
        G.add_node(row["apple_music_id"], key=row["key"], bpm=row["bpm"])

    # Build edges with per-song BPM tolerance
    for _, source_row in df.iterrows():
        source_id = source_row["apple_music_id"]
        source_key = source_row["key"]
        source_bpm = source_row["bpm"]

        connections = []

        # Get harmonically compatible keys
        compatible_keys = set()
        for relation_type in selected_relations:
            if source_key in key_type_relations[relation_type]:
                compatible_keys.update(key_type_relations[relation_type][source_key])

        # Find connections with increasing BPM tolerance
        for bpm_tolerance in range(4, 21):
            potential_targets = df[
                (df["key"].isin(compatible_keys))
                & (df["apple_music_id"] != source_id)
                & (abs(df["bpm"] - source_bpm) <= bpm_tolerance)
            ].copy()

            if len(potential_targets) >= 2:
                # Sort by BPM difference and take best matches
                potential_targets["bpm_diff"] = abs(
                    potential_targets["bpm"] - source_bpm
                )
                potential_targets = potential_targets.sort_values("bpm_diff").head(
                    max_connections
                )
                connections = potential_targets[
                    ["apple_music_id", "bpm_diff"]
                ].values.tolist()
                break

        # Add edges
        for target_id, bpm_diff in connections:
            G.add_edge(source_id, target_id, bpm_diff=bpm_diff)

    return G


def create_plotly_network(G, layout_type="spring"):
    """Create Plotly network visualization"""

    if layout_type == "spring":
        pos = nx.spring_layout(G, k=5, iterations=100, seed=42)
    elif layout_type == "force_directed":
        # Use community detection for clustering
        communities = nx.community.greedy_modularity_communities(G.to_undirected())

        # Create layout with community positioning
        pos = {}
        community_centers = []

        # Position communities in a circle
        num_communities = len(communities)
        for i, community in enumerate(communities):
            angle = 2 * math.pi * i / num_communities
            center_x = 3 * math.cos(angle)
            center_y = 3 * math.sin(angle)
            community_centers.append((center_x, center_y))

            # Position nodes within community using spring layout
            subgraph = G.subgraph(community)
            if len(community) > 1:
                sub_pos = nx.spring_layout(subgraph, k=1, iterations=50)
                for node in community:
                    pos[node] = (
                        center_x + sub_pos[node][0],
                        center_y + sub_pos[node][1],
                    )
            else:
                pos[list(community)[0]] = (center_x, center_y)
    else:  # circular
        pos = nx.circular_layout(G)

    # Extract edges
    edge_x, edge_y = [], []
    edge_info = []

    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

        bpm_diff = (
            G[edge[0]][edge[1]]["bpm_diff"] if "bpm_diff" in G[edge[0]][edge[1]] else 0
        )
        edge_info.append(f"{edge[0]} → {edge[1]}<br>BPM diff: {bpm_diff}")

    # Create edge trace
    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        line=dict(width=0.5, color="#888"),
        hoverinfo="none",
        mode="lines",
    )

    # Extract nodes
    node_x = [pos[node][0] for node in G.nodes()]
    node_y = [pos[node][1] for node in G.nodes()]

    node_info = []
    node_keys = []
    node_bpms = []

    for node in G.nodes():
        node_data = G.nodes[node]
        key = node_data.get("key", "Unknown")
        bpm = node_data.get("bpm", "Unknown")
        connections = len(list(G.neighbors(node)))

        node_info.append(
            f"{node}<br>Key: {key}<br>BPM: {bpm}<br>Connections: {connections}"
        )
        node_keys.append(key)
        node_bpms.append(bpm)

    # Create node trace with size based on connections
    node_sizes = [min(20, 8 + len(list(G.neighbors(node))) * 2) for node in G.nodes()]

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers",
        hoverinfo="text",
        text=node_info,
        marker=dict(
            showscale=True,
            colorscale="Viridis",
            size=node_sizes,
            color=node_keys,  # Color by key
            colorbar=dict(thickness=15, len=0.5, xanchor="left", title="Key"),
            line=dict(width=1, color="white"),
        ),
    )

    return [edge_trace, node_trace]


# Load data
df = pd.read_csv("songs.csv")

# Initialize Dash app
app = Dash(__name__)

app.layout = html.Div(
    [
        html.H1("Music Network Visualization", style={"textAlign": "center"}),
        html.Div(
            [
                html.Label("Select Harmonic Relationships:"),
                dcc.Checklist(
                    id="relation-selector",
                    options=[
                        {"label": "Matching", "value": "matching"},
                        {"label": "Boost", "value": "boost"},
                        {"label": "Boost Boost", "value": "boost boost"},
                        {"label": "Boost Boost Boost", "value": "boost boost boost"},
                    ],
                    value=["matching", "boost"],
                    inline=True,
                ),
            ],
            style={"margin": "20px"},
        ),
        html.Div(
            [
                html.Label("Layout Type:"),
                dcc.RadioItems(
                    id="layout-selector",
                    options=[
                        {"label": "Spring Layout", "value": "spring"},
                        {
                            "label": "Force Directed + Communities",
                            "value": "force_directed",
                        },
                        {"label": "Circular Layout", "value": "circular"},
                    ],
                    value="force_directed",
                    inline=True,
                ),
            ],
            style={"margin": "20px"},
        ),
        html.Div(
            [
                html.Label("Max Connections per Song:"),
                dcc.Slider(
                    id="connection-slider",
                    min=2,
                    max=8,
                    value=3,
                    marks={i: str(i) for i in range(2, 9)},
                    step=1,
                ),
            ],
            style={"margin": "20px"},
        ),
        dcc.Graph(id="network-graph", style={"height": "80vh"}),
        html.Div(id="graph-stats", style={"margin": "20px", "textAlign": "center"}),
    ]
)


@callback(
    [Output("network-graph", "figure"), Output("graph-stats", "children")],
    [
        Input("relation-selector", "value"),
        Input("layout-selector", "value"),
        Input("connection-slider", "value"),
    ],
)
def update_graph(selected_relations, layout_type, max_connections):
    if not selected_relations:
        selected_relations = ["matching"]

    # Build network
    G = build_network(df, selected_relations, max_connections)

    # Create visualization
    traces = create_plotly_network(G, layout_type)

    fig = go.Figure(
        data=traces,
        layout=go.Layout(
            title=dict(text="Song Network Graph", font=dict(size=16)),
            showlegend=False,
            hovermode="closest",
            margin=dict(b=20, l=5, r=5, t=40),
            annotations=[
                dict(
                    text="Hover over nodes for song info",
                    showarrow=False,
                    xref="paper",
                    yref="paper",
                    x=0.005,
                    y=-0.002,
                    xanchor="left",
                    yanchor="bottom",
                    font=dict(size=12),
                )
            ],
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            plot_bgcolor="white",
        ),
    )

    # Stats
    avg_connections = (
        G.number_of_edges() / G.number_of_nodes() if G.number_of_nodes() > 0 else 0
    )
    stats = f"Nodes: {G.number_of_nodes()} | Edges: {G.number_of_edges()} | Avg connections: {avg_connections:.1f}"

    return fig, stats


if __name__ == "__main__":
    app.run(debug=True)
