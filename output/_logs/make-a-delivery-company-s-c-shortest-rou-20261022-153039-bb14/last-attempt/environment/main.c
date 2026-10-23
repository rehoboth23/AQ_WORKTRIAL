#include "route.h"
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char** argv)
{
    if (argc != 4) {
        fprintf(stderr, "Usage: %s GRAPH_FILE SRC DST\n", argv[0]);
        return 2;
    }

    RouteGraph* g = route_load(argv[1]);
    if (!g) {
        fprintf(stderr, "Failed to load graph: %s\n", argv[1]);
        return 2;
    }

    int src = atoi(argv[2]);
    int dst = atoi(argv[3]);

    int* path    = NULL;
    int  path_len = 0;

    int result = route_find(g, src, dst, &path, &path_len);

    if (result != 0) {
        printf("unreachable\n");
        free(path);
        route_free(g);
        return 1;
    }

    for (int i = 0; i < path_len; i++) {
        if (i > 0) printf(" ");
        printf("%d", path[i]);
    }
    printf(" %ld\n", route_last_cost());

    free(path);
    route_free(g);
    return 0;
}
