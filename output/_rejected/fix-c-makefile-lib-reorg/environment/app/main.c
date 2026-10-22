#include <stdio.h>
#include <stdlib.h>
#include <graph/algo.h>
#include <graph/io.h>

int main(int argc, char *argv[]) {
    if (argc != 4) {
        fprintf(stderr, "Usage: %s <graph_file> <source_node> <dest_node>\n", argv[0]);
        return 1;
    }

    Graph *g = graph_load_from_file(argv[1]);
    if (!g) {
        fprintf(stderr, "Error: could not load graph from %s\n", argv[1]);
        return 1;
    }

    int src = atoi(argv[2]);
    int dst = atoi(argv[3]);

    double dist = shortest_path(g, src, dst);
    if (dist < 0) {
        printf("Shortest path from %d to %d: unreachable\n", src, dst);
    } else {
        printf("Shortest path from %d to %d: %f\n", src, dst, dist);
    }

    printf("Connected components: %d\n", connected_components(g));
    printf("Total edges: %d\n", graph_num_edges(g));

    graph_release(g);
    return 0;
}
