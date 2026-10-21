# gcomp - Graph Analysis Tool

A command-line tool for graph analysis using the libgraph library.

## Building

```
make
```

## Dependencies

Requires libgraph installed at `/usr/local`. The library provides:

- Header: `/usr/local/include/graph.h`
- Archive: `/usr/local/lib/libgraph.a`

Install libgraph from source, then run `make`.

## Usage

```
./gcomp <graph_file> <source_node> <dest_node>
```

## Input Format

The graph file format:

```
<num_nodes> <num_edges>
<src> <dst> <weight>
...
```

## Example

```
./gcomp data/sample.graph 0 3
```
