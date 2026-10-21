#include "io.h"
#include <stdio.h>
#include <stdlib.h>

Graph *graph_load_from_file(const char *filename) {
    FILE *f = fopen(filename, "r");
    if (!f) return NULL;

    int num_nodes, num_edges;
    if (fscanf(f, "%d %d", &num_nodes, &num_edges) != 2) {
        fclose(f);
        return NULL;
    }

    Graph *g = graph_create(num_nodes);
    for (int i = 0; i < num_edges; i++) {
        int src, dst;
        double weight;
        if (fscanf(f, "%d %d %lf", &src, &dst, &weight) != 3) break;
        graph_add_edge(g, src, dst, weight);
    }

    fclose(f);
    return g;
}

void graph_release(Graph *g) {
    graph_destroy(g);
}

int graph_num_edges(const Graph *g) {
    return graph_edge_count(g);
}
