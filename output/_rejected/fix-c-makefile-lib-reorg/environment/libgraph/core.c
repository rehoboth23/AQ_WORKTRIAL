#include "core.h"
#include <stdlib.h>
#include <string.h>

Graph *graph_create(int num_nodes) {
    Graph *g = malloc(sizeof(Graph));
    g->num_nodes = num_nodes;
    g->num_edges = 0;
    g->cap_edges = 64;
    g->edges = malloc(g->cap_edges * sizeof(Edge));
    return g;
}

void graph_destroy(Graph *g) {
    if (g) {
        free(g->edges);
        free(g);
    }
}

int graph_add_edge(Graph *g, int src, int dst, double weight) {
    if (g->num_edges >= g->cap_edges) {
        g->cap_edges *= 2;
        g->edges = realloc(g->edges, g->cap_edges * sizeof(Edge));
    }
    g->edges[g->num_edges++] = (Edge){src, dst, weight};
    return 0;
}

int graph_edge_count(const Graph *g) {
    return g->num_edges;
}

int graph_node_count(const Graph *g) {
    return g->num_nodes;
}
