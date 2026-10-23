#include "route.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>

/* ------------------------------------------------------------------ */
/*  Internal edge representation (singly-linked adjacency list)        */
/* ------------------------------------------------------------------ */

typedef struct Edge {
    int          to;
    long         weight;
    struct Edge* next;
} Edge;

/* ------------------------------------------------------------------ */
/*  RouteGraph definition                                             */
/* ------------------------------------------------------------------ */

struct RouteGraph {
    int    num_nodes;
    Edge** adj;          /* adj[u] -> linked list of edges from u       */
};

/* ------------------------------------------------------------------ */
/*  Module-level state for the counter / last-cost                     */
/* ------------------------------------------------------------------ */

static long g_relaxations = 0;
static long g_last_cost   = 0;

/* ------------------------------------------------------------------ */
/*  route_load                                                         */
/* ------------------------------------------------------------------ */

RouteGraph* route_load(const char* filename)
{
    FILE* f = fopen(filename, "r");
    if (!f) return NULL;

    int V, E;
    if (fscanf(f, "%d %d", &V, &E) != 2) { fclose(f); return NULL; }
    if (V < 0 || E < 0) { fclose(f); return NULL; }

    RouteGraph* g = (RouteGraph*)malloc(sizeof(RouteGraph));
    if (!g) { fclose(f); return NULL; }
    g->num_nodes = V;
    g->adj = (Edge**)calloc((size_t)V, sizeof(Edge*));
    if (!g->adj) { free(g); fclose(f); return NULL; }

    for (int i = 0; i < E; i++) {
        int u, v;
        long w;
        if (fscanf(f, "%d %d %ld", &u, &v, &w) != 3) break;
        if (u < 0 || u >= V || v < 0 || v >= V || w < 0) continue;

        Edge* e = (Edge*)malloc(sizeof(Edge));
        if (!e) break;
        e->to     = v;
        e->weight = w;
        e->next   = g->adj[u];
        g->adj[u] = e;
    }

    fclose(f);
    return g;
}

/* ------------------------------------------------------------------ */
/*  route_free                                                         */
/* ------------------------------------------------------------------ */

void route_free(RouteGraph* g)
{
    if (!g) return;
    for (int i = 0; i < g->num_nodes; i++) {
        Edge* e = g->adj[i];
        while (e) {
            Edge* nxt = e->next;
            free(e);
            e = nxt;
        }
    }
    free(g->adj);
    free(g);
}

/* ------------------------------------------------------------------ */
/*  route_find  (STUB — to be implemented)                            */
/*                                                                     */
/*  The original O(V²) Dijkstra was removed for performance work.      */
/*  Replace this stub with a fast implementation that:                 */
/*    • uses a binary min-heap (or better) keyed by distance           */
/*    • among equal-cost routes returns the lexicographically smallest */
/*      node-id sequence  (see route.h for the full rule)              */
/*    • does NOT terminate early when dst is extracted — zero-weight   */
/*      edges from later-processed nodes can yield a lex-smaller       */
/*      equal-cost path                                                */
/*    • counts only distance-value comparisons (route.h)               */
/* ------------------------------------------------------------------ */

int route_find(RouteGraph* g, int src, int dst,
               int** out_path, int* out_len)
{
    (void)g; (void)src; (void)dst;
    g_relaxations = 0;
    g_last_cost   = 0;

    *out_path = NULL;
    *out_len  = 0;
    return -1;   /* always "unreachable" until implemented */
}

/* ------------------------------------------------------------------ */
/*  route_relaxations / route_last_cost                                */
/* ------------------------------------------------------------------ */

long route_relaxations(void) { return g_relaxations; }
long route_last_cost(void)   { return g_last_cost;   }
