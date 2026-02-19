from bokeh.plotting import figure, curdoc, from_networkx
from bokeh.models import (
    HoverTool, Circle, MultiLine,
    NodesAndLinkedEdges, EdgesAndLinkedNodes,
    TextInput, Select
)
from bokeh.layouts import column, row
import networkx as nx
from neo4j import GraphDatabase
import os

# -------------------- 1. Connect to Neo4j (Aura Free) --------------------
# Use environment variables for credentials (safer for hosting)
NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+s://a9ee61f9.databases.neo4j.io")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "your_password_here")  # set in Render env
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

driver = GraphDatabase.driver(
    NEO4J_URI, 
    auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
)

def fetch_graph(rel_filter=None):
    query = """
    MATCH (n)-[r]->(m)
    RETURN elementId(n) AS source_id, labels(n)[0] AS source_label, properties(n) AS source_props,
           elementId(m) AS target_id, labels(m)[0] AS target_label, properties(m) AS target_props,
           type(r) AS rel_type
    """
    with driver.session(database=NEO4J_DATABASE) as session:
        records = session.run(query).data()

    if rel_filter and rel_filter != "ALL":
        records = [r for r in records if r["rel_type"] == rel_filter]

    return records

# -------------------- 2. Build Graph --------------------
def build_graph(rel_filter=None):
    data = fetch_graph(rel_filter)

    nodes = {}
    edges = []

    for row in data:
        sid = row["source_id"]
        tid = row["target_id"]

        if sid not in nodes:
            nodes[sid] = {"label": row["source_label"], **row["source_props"]}
        if tid not in nodes:
            nodes[tid] = {"label": row["target_label"], **row["target_props"]}

        edges.append((sid, tid, row["rel_type"]))

    G = nx.Graph()

    for nid, props in nodes.items():
        props["name"] = props.get("name", "")
        props["title"] = props.get("title", "")
        G.add_node(nid, **props)

    for s, t, rel in edges:
        G.add_edge(s, t, rel=rel)

    return G

# -------------------- 3. Create Plot --------------------
def create_plot(G):
    pos = nx.spring_layout(G, seed=42)

    plot = figure(
        title="Neo4j Interactive Graph Explorer",
        tools="pan,wheel_zoom,reset,save,hover",
        match_aspect=True
    )

    graph_renderer = from_networkx(G, pos)

    # ---- Color nodes by label ----
    node_source = graph_renderer.node_renderer.data_source

    node_colors = []
    for nid in node_source.data['index']:
        label = G.nodes[nid].get("label", "")
        if label == "Person":
            node_colors.append("blue")
        elif label == "Movie":
            node_colors.append("green")
        else:
            node_colors.append("gray")

    node_source.data["node_color"] = node_colors

    graph_renderer.node_renderer.glyph = Circle(radius=0.03, fill_color="node_color", fill_alpha=0.8)
    graph_renderer.node_renderer.hover_glyph = Circle(radius=0.05, fill_color="orange", fill_alpha=1.0)
    graph_renderer.node_renderer.selection_glyph = Circle(radius=0.05, fill_color="red", fill_alpha=1.0)

    # ---- Color edges by relationship ----
    edge_source = graph_renderer.edge_renderer.data_source

    edge_colors = []
    for e in G.edges:
        rel = G.edges[e]["rel"]
        if rel == "ACTED_IN":
            edge_colors.append("red")
        elif rel == "DIRECTED":
            edge_colors.append("yellow")
        elif rel == "PRODUCED":
            edge_colors.append("green")
        else:
            edge_colors.append("gray")

    edge_source.data["edge_color"] = edge_colors

    graph_renderer.edge_renderer.glyph = MultiLine(line_color="edge_color", line_width=2)
    graph_renderer.edge_renderer.hover_glyph = MultiLine(line_color="orange", line_width=4)
    graph_renderer.edge_renderer.selection_glyph = MultiLine(line_color="blue", line_width=4)

    # Highlight neighbors
    graph_renderer.selection_policy = NodesAndLinkedEdges()
    graph_renderer.inspection_policy = EdgesAndLinkedNodes()

    # ---- Copy node attributes for hover ----
    labels, names, titles = [], [], []
    for nid in node_source.data['index']:
        node_data = G.nodes[nid]
        labels.append(node_data.get('label', ''))
        names.append(node_data.get('name', ''))
        titles.append(node_data.get('title', ''))

    node_source.data['label'] = labels
    node_source.data['name'] = names
    node_source.data['title'] = titles

    # ---- Copy edge attributes for hover ----
    edge_source.data['rel'] = [G.edges[e]['rel'] for e in G.edges]

    # Hover tools
    plot.add_tools(HoverTool(
        tooltips=[("Label", "@label"), ("Name", "@name"), ("Title", "@title")],
        renderers=[graph_renderer.node_renderer]
    ))

    plot.add_tools(HoverTool(
        tooltips=[("Relation", "@rel")],
        renderers=[graph_renderer.edge_renderer]
    ))

    plot.renderers.append(graph_renderer)
    return plot

# -------------------- 4. UI Controls --------------------
search_box = TextInput(title="Search (Name or Title):")
rel_filter = Select(title="Filter by Relationship",
                    value="ALL",
                    options=["ALL", "ACTED_IN", "DIRECTED", "PRODUCED"])

plot = create_plot(build_graph())

def update_graph(attr, old, new):
    keyword = search_box.value.lower()
    rel = rel_filter.value

    G_new = build_graph(rel)

    if keyword:
        G_new = G_new.subgraph([
            n for n, d in G_new.nodes(data=True)
            if keyword in d.get("name", "").lower()
            or keyword in d.get("title", "").lower()
        ]).copy()

    layout.children[1] = create_plot(G_new)

search_box.on_change("value", update_graph)
rel_filter.on_change("value", update_graph)

layout = row(column(search_box, rel_filter), plot)
curdoc().add_root(layout)

