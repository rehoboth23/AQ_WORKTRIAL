#ifndef GRAPH_IO_H
#define GRAPH_IO_H

#include "core.h"

Graph *graph_load_from_file(const char *filename);
void graph_release(Graph *g);
int graph_num_edges(const Graph *g);

#endif
