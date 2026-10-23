#ifndef ROUTE_H
#define ROUTE_H

/*
 * SpeedyDeliver Route Library — Public API
 *
 * This library computes shortest routes in a directed graph with
 * non-negative integer edge weights (including zero).
 *
 * Tie-breaking rule
 * -----------------
 * Among equal-cost routes, the one whose node-id sequence is
 * lexicographically smallest is returned.  Comparison is element-by-
 * element from the source; a shorter sequence that is a prefix of a
 * longer one is considered smaller.
 *
 *   Example: path [0, 1, 3]  vs  path [0, 1, 2, 3]
 *     At position 2 the first has 3, the second has 2; 2 < 3,
 *     so [0, 1, 2, 3] is lexicographically smaller.
 *
 * Relaxation counter
 * ------------------
 * route_relaxations() returns the number of *distance-value*
 * comparisons performed during the most recent route_find() call.
 *
 * A distance-value comparison is any comparison where at least one
 * operand is a node's current shortest-path distance estimate.
 * Comparisons of node identifiers, array indices, or path arrays
 * for tie-breaking are NOT counted.
 *
 *   Examples of counted comparisons:
 *     - dist[i] < current_min   (scan in O(V²) Dijkstra)
 *     - dist[u] + w < dist[v]   (edge relaxation)
 *     - dist[u] + w == dist[v]  (equal-cost edge check)
 *     - heap-key comparisons where the key is a distance value
 *       (sift-up / sift-down in a binary-heap Dijkstra)
 *
 *   Examples of NOT counted comparisons:
 *     - node-id tie-breaking in the heap key
 *     - lexicographic path comparisons for tie-breaking
 *     - array-index bounds checks
 */

typedef struct RouteGraph RouteGraph;

/* Load a graph from a text file.
 * Format: first line "V E", then E lines "u v w".
 * Node ids are 0 .. V-1.  Weights are non-negative integers.
 * Returns NULL on error. */
RouteGraph* route_load(const char* filename);

/* Free a graph loaded by route_load. */
void route_free(RouteGraph* g);

/* Find the shortest path from src to dst.
 *
 * On success returns 0; *out_path is set to a malloc'd array of
 * node ids and *out_len to its length.  Caller must free *out_path.
 *
 * If dst is unreachable from src, returns -1 and sets *out_path to
 * NULL and *out_len to 0.
 *
 * Among equal-cost routes the lexicographically smallest node-id
 * sequence is returned (see above). */
int route_find(RouteGraph* g, int src, int dst,
               int** out_path, int* out_len);

/* Return the number of distance-value comparisons from the most
 * recent route_find() call (see definition above). */
long route_relaxations(void);

/* Return the total cost of the most recent successful route_find()
 * call.  Value is undefined after an unsuccessful call. */
long route_last_cost(void);

#endif /* ROUTE_H */
