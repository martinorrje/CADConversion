import graphviz
import json
import os


def create_graph(json_file, graph_type):
    with open(json_file, 'r') as file:
        data = json.load(file)

    # Create a new directed graph
    graph = graphviz.Digraph(format='png')

    # Add the vertices (nodes)
    for vertex in data[graph_type]['vertices']:
        graph.node(vertex['name'])

    # Add the edges
    for edge in data[graph_type]['edges']:
        graph.edge(edge['from'], edge['to'], label=edge['label'])

    # Save the graph to a file
    graph.render(filename=f'{graph_type}', directory=os.path.dirname(json_file) + '/', cleanup=True)
