#ifndef GRAPH_CORE_H
#define GRAPH_CORE_H

typedef struct {
    int src;
    int dst;
    double weight;
} Edge;

typedef struct Graph {
    int num_nodes;
    int num_edges;
    int cap_edges;
    Edge *edges;
} Graph;

Graph *graph_create(int num_nodes);
void graph_destroy(Graph *g);
int graph_add_edge(Graph *g, int src, int dst, double weight);
int graph_edge_count(const Graph *g);
int graph_node_count(const Graph *g);

#endif
