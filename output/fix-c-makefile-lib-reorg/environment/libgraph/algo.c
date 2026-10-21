#include "algo.h"
#include <float.h>
#include <stdlib.h>

static int find_root(int *parent, int x) {
    while (parent[x] != x) {
        parent[x] = parent[parent[x]];
        x = parent[x];
    }
    return x;
}

static void unite(int *parent, int a, int b) {
    int ra = find_root(parent, a);
    int rb = find_root(parent, b);
    if (ra != rb) parent[ra] = rb;
}

double shortest_path(const Graph *g, int src, int dst) {
    int n = g->num_nodes;
    double *dist = malloc(n * sizeof(double));
    int *visited = calloc(n, sizeof(int));
    for (int i = 0; i < n; i++) dist[i] = DBL_MAX;
    dist[src] = 0.0;

    for (int iter = 0; iter < n; iter++) {
        int u = -1;
        double mindist = DBL_MAX;
        for (int i = 0; i < n; i++) {
            if (!visited[i] && dist[i] < mindist) {
                mindist = dist[i];
                u = i;
            }
        }
        if (u == -1) break;
        visited[u] = 1;
        for (int i = 0; i < g->num_edges; i++) {
            if (g->edges[i].src == u) {
                int v = g->edges[i].dst;
                double w = g->edges[i].weight;
                if (dist[u] + w < dist[v]) {
                    dist[v] = dist[u] + w;
                }
            }
        }
    }

    double result = dist[dst];
    free(dist);
    free(visited);
    return (result == DBL_MAX) ? -1.0 : result;
}

int connected_components(const Graph *g) {
    int n = g->num_nodes;
    int *parent = malloc(n * sizeof(int));
    for (int i = 0; i < n; i++) parent[i] = i;

    for (int i = 0; i < g->num_edges; i++) {
        unite(parent, g->edges[i].src, g->edges[i].dst);
    }

    int count = 0;
    for (int i = 0; i < n; i++) {
        if (find_root(parent, i) == i) count++;
    }

    free(parent);
    return count;
}
