The `gcomp` tool in /app fails to build — `make` errors out after the libgraph library was reorganized from a single monolithic archive into three sub-libraries (core, algo, io). The application source code (main.c) has already been updated for the new include style (`<graph/algo.h>`, `<graph/io.h>`), but the Makefile still references the old library layout.

Fix the Makefile so that `make` completes successfully and `./gcomp` works correctly. Do not modify any .c or .h files — only change the Makefile.

The binary is invoked as: `./gcomp <graph_file> <source_node> <dest_node>`

Sample data is in `data/sample.graph`. Expected outputs:

- `./gcomp data/sample.graph 0 3` → Shortest path from 0 to 3: 6.000000 / Connected components: 1 / Total edges: 8
- `./gcomp data/sample.graph 3 0` → Shortest path from 3 to 0: unreachable / Connected components: 1 / Total edges: 8
